# -*- coding: utf-8 -*-
import logging
from markupsafe import Markup
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # -------------------------------------------------------
    # Override state field to inject 'draft_indent' state
    # We use 'draft_indent' internally to avoid conflict with
    # the standard Odoo 'draft' state alias used for RFQ.
    # The status bar will display it as "Draft".
    # -------------------------------------------------------
    # state = fields.Selection(
    #     selection_add=[('draft_indent', 'Draft')],
    #     ondelete={'draft_indent': 'cascade'},
    # )
    partner_id = fields.Many2one(
        'res.partner',
        string="Vendor",
        required=False
    )
    state = fields.Selection([
        ('draft_indent', 'Draft'),
        ('draft', 'RFQ'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft_indent', tracking=True)

    approval_state = fields.Selection([
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
    ], string='Approval Status', copy=False, tracking=True)

    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        copy=False,
        readonly=True,
    )

    approval_date = fields.Datetime(
        string='Approval Date',
        copy=False,
        readonly=True,
    )

    # Dynamic role flags for UI button visibility
    is_current_store_user = fields.Boolean(
        string='Current User is Store User',
        compute='_compute_current_user_roles',
    )
    is_current_purchase_user = fields.Boolean(
        string='Current User is Purchase User',
        compute='_compute_current_user_roles',
    )
    user_has_store_indent = fields.Boolean(
        string='User Has Store Indent',
        compute='_compute_current_user_roles',
    )

    # -------------------------------------------------------
    # Compute
    # -------------------------------------------------------
    @api.depends_context('uid')
    def _compute_current_user_roles(self):
        u = self.env.user
        is_sys_admin = u._is_admin() or u.has_group('base.group_system')
        store_user_flag = bool(getattr(u, 'is_store_user', False))
        purchase_user_flag = bool(getattr(u, 'is_purchase_user', False))

        if purchase_user_flag and not store_user_flag and not is_sys_admin:
            store_flag = False
        elif is_sys_admin or store_user_flag:
            store_flag = True
        else:
            store_flag = bool(u.has_group('stock.group_stock_user') and not purchase_user_flag)

        purchase_flag = bool(
            purchase_user_flag
            or u.has_group('purchase.group_purchase_manager')
            or is_sys_admin
        )
        for order in self:
            order.is_current_store_user = store_flag
            order.is_current_purchase_user = purchase_flag
            order.user_has_store_indent = False

    def action_view_picking(self):
        self._compute_current_user_roles()
        for order in self:
            if not order.is_current_store_user:
                raise UserError(_("Only Store Users and Administrators can access receipts or receive products."))
        return super().action_view_picking()

    # -------------------------------------------------------
    # Override create: start from 'draft_indent' not 'draft'
    # -------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Force new purchase orders into our custom Draft state
            if vals.get('state', 'draft') == 'draft':
                vals['state'] = 'draft_indent'
        orders = super().create(vals_list)
        return orders

    def _send_role_notification(self, recipient_users, body, subject, summary, note):
        """
        Sends notifications to recipient_users through all Odoo channels:
        1. Chatter post on the purchase order record
        2. Force Discuss Inbox notification (mail.notification type='inbox')
        3. Real-time bus send for instant notification badge update
        4. Direct Message chat in discuss.channel (sounds chime & increments navbar chat icon)
        5. To-Do Activity scheduled in systray clock
        """
        recipients = recipient_users.filtered(lambda u: u.active and u.partner_id)
        if not recipients:
            return

        partner_ids = recipients.mapped('partner_id').ids
        author_id = self.env.user.partner_id.id if self.env.user.partner_id else False

        # 1. Post to Chatter
        msg = self.message_post(
            body=body,
            subject=subject,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            partner_ids=partner_ids,
        )

        todo_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        todo_type_id = todo_type.id if todo_type else False

        for user in recipients:
            # 2. Force Discuss Inbox Notification
            try:
                notif = self.env['mail.notification'].sudo().search([
                    ('mail_message_id', '=', msg.id),
                    ('res_partner_id', '=', user.partner_id.id),
                ], limit=1)
                if notif:
                    notif.sudo().write({'notification_type': 'inbox', 'is_read': False})
                else:
                    self.env['mail.notification'].sudo().create({
                        'mail_message_id': msg.id,
                        'res_partner_id': user.partner_id.id,
                        'notification_type': 'inbox',
                        'notification_status': 'sent',
                        'is_read': False,
                    })
            except Exception as e:
                _logger.warning("Could not create inbox notification for user %s: %s", user.name, e)

            # 3. Bus Notification for live Discuss Inbox update
            try:
                from odoo.addons.mail.tools.discuss import Store
                store = Store(bus_channel=user).add(msg.with_user(user))
                user._bus_send(
                    'mail.message/inbox',
                    {
                        'message_id': msg.id,
                        'store_data': store.get_result(),
                    },
                )
            except Exception:
                pass

            # 4. Direct Message in Discuss chat (triggers top navbar icon & notification popup)
            if user.partner_id.id != author_id:
                try:
                    chat = self.env['discuss.channel'].sudo()._get_or_create_chat(
                        partners_to=[user.partner_id.id], pin=True
                    )
                    if chat:
                        chat.sudo().message_post(
                            body=body,
                            message_type='comment',
                            subtype_xmlid='mail.mt_comment',
                            author_id=author_id,
                        )
                except Exception as e:
                    _logger.warning("Could not send chat message to user %s: %s", user.name, e)

            # 5. Schedule Activity in Systray Clock
            if todo_type_id:
                try:
                    existing_act = self.env['mail.activity'].sudo().search([
                        ('res_model', '=', self._name),
                        ('res_id', '=', self.id),
                        ('user_id', '=', user.id),
                        ('activity_type_id', '=', todo_type_id),
                    ], limit=1)
                    if not existing_act:
                        self.sudo().activity_schedule(
                            activity_type_id=todo_type_id,
                            user_id=user.id,
                            summary=summary,
                            note=note,
                        )
                except Exception as e:
                    _logger.warning("Could not schedule activity for user %s: %s", user.name, e)

    # -------------------------------------------------------
    # Button: Request RFQ Approval (Store User submits to Purchase Users)
    # -------------------------------------------------------
    def button_request_rfq_approval(self):
        """
        Called when the user clicks 'Submit Approval' in Draft state.
        Validates product lines, then sends an approval request
        to Purchase Users.
        """
        self.ensure_one()

        if self.state != 'draft_indent':
            raise UserError(_("Only orders in Draft state can be submitted for approval."))

        # Check if there are any order lines
        if not self.order_line:
            raise ValidationError(
                _("Please add at least one product line before submitting for approval.")
            )

        # Find Purchase Users
        purchase_users = self.env['res.users'].search([
            ('is_purchase_user', '=', True),
            ('active', '=', True),
        ])
        if not purchase_users:
            # Fallback to purchase managers if no purchase users configured yet
            purchase_admin_group = self.env.ref(
                'purchase.group_purchase_manager', raise_if_not_found=False
            )
            if purchase_admin_group:
                purchase_users = purchase_admin_group.user_ids.filtered(lambda u: u.active)

        if not purchase_users:
            raise UserError(
                _("No Purchase User found. Please assign at least one user as 'Purchase User' in User Settings.")
            )

        # Set approval state to pending
        self.write({
            'approval_state': 'pending',
        })

        recipients = purchase_users.filtered(lambda u: u.id != self.env.user.id and u.partner_id)
        body = Markup(
            "%(user)s has submitted Purchase Order "
            "<b>%(name)s</b> for approval.<br/>"
            "Purchase Users: please review and approve or refuse."
        ) % {
            'user': self.env.user.name,
            'name': self.name,
        }
        subject = _("PO Approval Request: %s") % self.name
        summary = _("PO Approval Required: %s") % self.name
        note = _(
            "Purchase Order %(name)s was submitted for approval by %(user)s. "
            "Please review and approve or refuse.",
            name=self.name,
            user=self.env.user.name,
        )
        self._send_role_notification(recipients, body, subject, summary, note)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Approval Submitted"),
                'message': _(
                    "Purchase Order %s has been submitted to Purchase Users for approval.",
                    self.name
                ),
                'type': 'success',
                'sticky': False,
            }
        }

    # -------------------------------------------------------
    # Button: Approve RFQ (Purchase Users)
    # -------------------------------------------------------
    def button_approve_rfq(self):
        """
        Purchase User approves the RFQ request.
        Moves the order from draft_indent -> draft (RFQ state).
        Sends notification and activity back to the Store User who created it.
        """
        self.ensure_one()

        u = self.env.user
        is_admin = u.has_group('base.group_system') or u.has_group('purchase.group_purchase_manager')
        is_purchase = getattr(u, 'is_purchase_user', False)
        if not (is_purchase or is_admin):
            raise UserError(
                _("Only Purchase Users can approve RFQ requests.")
            )

        if self.state != 'draft_indent':
            raise UserError(_("Only Draft orders can be approved."))

        if self.approval_state != 'pending':
            raise UserError(_("This order does not have a pending approval request."))

        # Mark purchase user activities as done
        self.activity_ids.filtered(
            lambda a: a.user_id == self.env.user
        ).action_feedback(
            feedback=_("RFQ Approved by Purchase User %s", self.env.user.name)
        )

        self.write({
            'state': 'draft',          # Standard Odoo RFQ state
            'approval_state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now(),
        })

        # Notify Store Users (creator + all active is_store_user)
        store_users = self.env['res.users'].sudo().search([
            ('active', '=', True),
            ('is_store_user', '=', True),
        ])
        if self.create_uid and self.create_uid.active:
            store_users |= self.create_uid
        recipients = store_users.filtered(lambda u: u.id != self.env.user.id and u.partner_id)

        body = Markup(
            "<b>RFQ Approved</b> by Purchase User %(manager)s.<br/>"
            "Purchase Order <b>%(name)s</b> has moved to <b>RFQ</b> state."
        ) % {
            'manager': self.env.user.name,
            'name': self.name,
        }
        subject = _("RFQ Approved: %s") % self.name
        summary = _("RFQ Approved: %s") % self.name
        note = _(
            "Your Purchase Order %(name)s has been approved by Purchase User %(user)s and moved to RFQ.",
            name=self.name,
            user=self.env.user.name,
        )
        self._send_role_notification(recipients, body, subject, summary, note)

    # -------------------------------------------------------
    # Button: Refuse RFQ (Purchase Users)
    # -------------------------------------------------------
    def button_refuse_rfq(self):
        """
        Purchase User refuses the RFQ request.
        Order stays in draft_indent state.
        Sends notification and activity back to the Store User who created it.
        """
        self.ensure_one()

        u = self.env.user
        is_admin = u.has_group('base.group_system') or u.has_group('purchase.group_purchase_manager')
        is_purchase = getattr(u, 'is_purchase_user', False)
        if not (is_purchase or is_admin):
            raise UserError(
                _("Only Purchase Users can refuse RFQ requests.")
            )

        if self.approval_state != 'pending':
            raise UserError(_("This order does not have a pending approval request."))

        # Mark activities as done
        self.activity_ids.filtered(
            lambda a: a.user_id == self.env.user
        ).action_feedback(
            feedback=_("RFQ Refused by Purchase User %s", self.env.user.name)
        )

        self.write({
            'approval_state': 'refused',
        })

        # Notify Store Users (creator + all active is_store_user)
        store_users = self.env['res.users'].sudo().search([
            ('active', '=', True),
            ('is_store_user', '=', True),
        ])
        if self.create_uid and self.create_uid.active:
            store_users |= self.create_uid
        recipients = store_users.filtered(lambda u: u.id != self.env.user.id and u.partner_id)

        body = Markup(
            "<b>RFQ Refused</b> by Purchase User %(manager)s.<br/>"
            "Purchase Order <b>%(name)s</b> remains in <b>Draft</b> state. Please revise and re-submit."
        ) % {
            'manager': self.env.user.name,
            'name': self.name,
        }
        subject = _("RFQ Refused: %s") % self.name
        summary = _("RFQ Refused: %s") % self.name
        note = _(
            "Your Purchase Order %(name)s was refused by Purchase User %(user)s. "
            "Please review and re-submit approval.",
            name=self.name,
            user=self.env.user.name,
        )
        self._send_role_notification(recipients, body, subject, summary, note)

    # -------------------------------------------------------
    # Button: Reset to Draft (from refused state)
    # -------------------------------------------------------
    def button_reset_to_draft(self):
        """Allow re-submitting approval after refusal."""
        self.ensure_one()
        if self.state == 'draft_indent' and self.approval_state == 'refused':
            self.write({'approval_state': False})
        else:
            raise UserError(
                _("Only refused Draft orders can be reset for re-approval.")
            )

    # -------------------------------------------------------
    # Override: Confirm Order - only Purchase Users can confirm
    # -------------------------------------------------------
    def button_confirm(self):
        for order in self:
            if order.state == 'draft_indent':
                raise UserError(
                    _("Please submit for approval first before confirming "
                      "Purchase Order %s.", order.name)
                )
            if not order.partner_id:
                raise ValidationError(
                    _("Please set a Vendor before confirming Purchase Order %s.", order.name)
                )
            u = self.env.user
            is_admin = u.has_group('base.group_system') or u.has_group('purchase.group_purchase_manager')
            is_purchase = getattr(u, 'is_purchase_user', False)
            if not (is_purchase or is_admin):
                raise UserError(
                    _("Store Users are not authorized to confirm Purchase Orders. "
                      "Only Purchase Users can confirm this order.")
                )
            # Complete any pending Purchase activities on this order
            order.activity_ids.filtered(
                lambda a: a.user_id == self.env.user
            ).action_feedback(
                feedback=_("Purchase Order confirmed by %s", self.env.user.name)
            )
        return super().button_confirm()

    # -------------------------------------------------------
    # Override: Cancel should also handle draft_indent
    # -------------------------------------------------------
    def button_cancel(self):
        for order in self:
            if order.state == 'draft_indent':
                order.write({
                    'state': 'cancel',
                    'approval_state': False,
                })
                # Cancel pending activities
                order.activity_ids.unlink()
                order.message_post(
                    body=Markup("Purchase Order <b>%s</b> cancelled from Draft state.") % order.name,
                    subtype_xmlid='mail.mt_comment',
                )
                return True
        return super().button_cancel()

    # -------------------------------------------------------
    # Override name_get for display
    # -------------------------------------------------------
    def _get_report_base_filename(self):
        self.ensure_one()
        return 'Purchase Order - %s' % self.name
