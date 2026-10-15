# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


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
    def _compute_current_user_roles(self):
        u = self.env.user
        is_admin = u.has_group('base.group_system') or u.has_group('purchase.group_purchase_manager')
        store_flag = bool(getattr(u, 'is_store_user', False) or is_admin)
        purchase_flag = bool(getattr(u, 'is_purchase_user', False) or is_admin)
        for order in self:
            order.is_current_store_user = store_flag
            order.is_current_purchase_user = purchase_flag
            order.user_has_store_indent = False

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

        # Post a message and notify purchase users
        partner_ids = purchase_users.mapped('partner_id').ids
        body = Markup(
            "%(user)s has submitted Purchase Order "
            "<b>%(name)s</b> for approval. "
            "Purchase Users: please review and approve or refuse."
        ) % {
            'user': self.env.user.name,
            'name': self.name,
        }
        self.message_post(
            body=body,
            subject=_("PO Approval Request: %s", self.name),
            partner_ids=partner_ids,
            subtype_xmlid='mail.mt_comment',
        )

        # Schedule activity for each purchase user
        activity_type = self.env.ref(
            'purchase_draft_approval.mail_activity_rfq_approval',
            raise_if_not_found=False,
        )
        activity_type_id = activity_type.id if activity_type else self.env.ref(
            'mail.mail_activity_data_todo'
        ).id

        for user in purchase_users:
            self.activity_schedule(
                activity_type_id=activity_type_id,
                summary=_("PO Approval Required: %s", self.name),
                note=_(
                    "Purchase Order %(name)s was submitted for approval by %(user)s. "
                    "Please review and approve or refuse.",
                    name=self.name,
                    user=self.env.user.name,
                ),
                user_id=user.id,
            )

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

        # Notify Store User (the creator)
        creator = self.create_uid
        partner_ids = [creator.partner_id.id] if creator and creator.partner_id else []

        body = Markup(
            "<b>RFQ Approved</b> by Purchase User %(manager)s.<br/>"
            "Purchase Order <b>%(name)s</b> has moved to <b>RFQ</b> state."
        ) % {
            'manager': self.env.user.name,
            'name': self.name,
        }
        self.message_post(
            body=body,
            partner_ids=partner_ids,
            subtype_xmlid='mail.mt_comment',
        )

        # Schedule notification activity for the Store User who created it
        if creator and creator != self.env.user:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                summary=_("RFQ Approved: %s", self.name),
                note=_(
                    "Your Purchase Order %(name)s has been approved by Purchase User %(user)s and moved to RFQ.",
                    name=self.name,
                    user=self.env.user.name,
                ),
                user_id=creator.id,
            )

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

        creator = self.create_uid
        partner_ids = [creator.partner_id.id] if creator and creator.partner_id else []

        body = Markup(
            "<b>RFQ Refused</b> by Purchase User %(manager)s.<br/>"
            "Purchase Order <b>%(name)s</b> remains in <b>Draft</b> state. Please revise and re-submit."
        ) % {
            'manager': self.env.user.name,
            'name': self.name,
        }
        self.message_post(
            body=body,
            partner_ids=partner_ids,
            subtype_xmlid='mail.mt_comment',
        )

        # Schedule notification activity for the Store User who created it
        if creator and creator != self.env.user:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                summary=_("RFQ Refused: %s", self.name),
                note=_(
                    "Your Purchase Order %(name)s was refused by Purchase User %(user)s. "
                    "Please review and re-submit approval.",
                    name=self.name,
                    user=self.env.user.name,
                ),
                user_id=creator.id,
            )

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
