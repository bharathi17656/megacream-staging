# -*- coding: utf-8 -*-
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
    # Button: Request RFQ Approval (sends approval request to Store Users)
    # -------------------------------------------------------
    def button_request_rfq_approval(self):
        """
        Called when the user clicks 'Send to RFQ' in Draft state.
        Validates product lines, then sends an approval request
        to Store Users.
        """
        self.ensure_one()

        if self.state != 'draft_indent':
            raise UserError(_("Only orders in Draft state can be sent for RFQ approval."))

        # Check if there are any order lines
        if not self.order_line:
            raise ValidationError(
                _("Please add at least one product line before requesting RFQ approval.")
            )

        # Find Store Users
        store_users = self.env['res.users'].search([
            ('is_store_user', '=', True),
            ('active', '=', True),
        ])
        if not store_users:
            # Fallback to purchase managers if no store users are configured
            purchase_admin_group = self.env.ref(
                'purchase.group_purchase_manager', raise_if_not_found=False
            )
            if purchase_admin_group:
                store_users = purchase_admin_group.user_ids.filtered(lambda u: u.active)

        if not store_users:
            raise UserError(
                _("No Store User found. Please assign at least one user as 'Store User' in User Settings.")
            )

        # Set approval state to pending
        self.write({
            'approval_state': 'pending',
        })

        # Post a message and notify store users
        partner_ids = store_users.mapped('partner_id').ids
        self.message_post(
            body=_(
                "%(user)s has requested approval to move Purchase Order "
                "<b>%(name)s</b> from <b>Draft</b> to <b>RFQ</b> state. "
                "Store Users: please review and approve or refuse.",
                user=self.env.user.name,
                name=self.name,
            ),
            subject=_("RFQ Approval Request: %s", self.name),
            partner_ids=partner_ids,
            subtype_xmlid='mail.mt_comment',
        )

        # Schedule activity for each store user
        activity_type = self.env.ref(
            'purchase_draft_approval.mail_activity_rfq_approval',
            raise_if_not_found=False,
        )
        activity_type_id = activity_type.id if activity_type else self.env.ref(
            'mail.mail_activity_data_todo'
        ).id

        for user in store_users:
            self.activity_schedule(
                activity_type_id=activity_type_id,
                summary=_("RFQ Approval Required: %s", self.name),
                note=_(
                    "Purchase Order %(name)s is waiting for Store User approval "
                    "to move to RFQ state. Created by: %(user)s",
                    name=self.name,
                    user=self.env.user.name,
                ),
                user_id=user.id,
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Approval Requested"),
                'message': _(
                    "Your request to move %s to RFQ has been sent to Store Users for approval.",
                    self.name
                ),
                'type': 'success',
                'sticky': False,
            }
        }

    # -------------------------------------------------------
    # Button: Approve RFQ (Store Users)
    # -------------------------------------------------------
    def button_approve_rfq(self):
        """
        Store User approves the RFQ request.
        Moves the order from draft_indent -> draft (RFQ state).
        Then notifies Purchase Users that the PO is ready for continuation and confirmation.
        """
        self.ensure_one()

        u = self.env.user
        is_admin = u.has_group('base.group_system') or u.has_group('purchase.group_purchase_manager')
        is_store = getattr(u, 'is_store_user', False)
        if not (is_store or is_admin):
            raise UserError(
                _("Only Store Users can approve RFQ requests.")
            )

        if self.state != 'draft_indent':
            raise UserError(_("Only Draft orders can be approved for RFQ."))

        if self.approval_state != 'pending':
            raise UserError(_("This order does not have a pending approval request."))

        # Mark store user activities as done
        self.activity_ids.filtered(
            lambda a: a.user_id == self.env.user
        ).action_feedback(
            feedback=_("RFQ Approved by Store User %s", self.env.user.name)
        )

        self.write({
            'state': 'draft',          # Standard Odoo RFQ state
            'approval_state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now(),
        })

        self.message_post(
            body=_(
                "<b>RFQ Approved</b> by Store User %(manager)s. "
                "Purchase Order <b>%(name)s</b> has moved to <b>RFQ</b> state. "
                "Purchase Users can now continue processing the order.",
                manager=self.env.user.name,
                name=self.name,
            ),
            subtype_xmlid='mail.mt_comment',
        )

        # Notify and schedule activity for Purchase Users
        purchase_users = self.env['res.users'].search([
            ('is_purchase_user', '=', True),
            ('active', '=', True),
        ])
        if not purchase_users:
            purchase_admin_group = self.env.ref('purchase.group_purchase_manager', raise_if_not_found=False)
            if purchase_admin_group:
                purchase_users = purchase_admin_group.user_ids.filtered(lambda u: u.active)

        todo_type_id = self.env.ref('mail.mail_activity_data_todo').id
        for p_user in purchase_users:
            self.activity_schedule(
                activity_type_id=todo_type_id,
                summary=_("RFQ Approved: %s ready for PO processing", self.name),
                note=_(
                    "Purchase Order %(name)s was approved by Store User %(store_user)s. "
                    "Please review vendor, pricing, and continue with PO confirmation.",
                    name=self.name,
                    store_user=self.env.user.name,
                ),
                user_id=p_user.id,
            )

    # -------------------------------------------------------
    # Button: Refuse RFQ (Store Users)
    # -------------------------------------------------------
    def button_refuse_rfq(self):
        """
        Store User refuses the RFQ request.
        Order stays in draft_indent state.
        """
        self.ensure_one()

        u = self.env.user
        is_admin = u.has_group('base.group_system') or u.has_group('purchase.group_purchase_manager')
        is_store = getattr(u, 'is_store_user', False)
        if not (is_store or is_admin):
            raise UserError(
                _("Only Store Users can refuse RFQ requests.")
            )

        if self.approval_state != 'pending':
            raise UserError(_("This order does not have a pending approval request."))

        # Mark activities as done
        self.activity_ids.filtered(
            lambda a: a.user_id == self.env.user
        ).action_feedback(
            feedback=_("RFQ Refused by Store User %s", self.env.user.name)
        )

        self.write({
            'approval_state': 'refused',
        })

        self.message_post(
            body=_(
                "<b>RFQ Refused</b> by Store User %(manager)s. "
                "Purchase Order <b>%(name)s</b> remains in <b>Draft</b> state. "
                "Please revise and re-request approval.",
                manager=self.env.user.name,
                name=self.name,
            ),
            subtype_xmlid='mail.mt_comment',
        )

    # -------------------------------------------------------
    # Button: Reset to Draft (from refused state)
    # -------------------------------------------------------
    def button_reset_to_draft(self):
        """Allow re-requesting approval after refusal."""
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
                    _("Please request RFQ approval first before confirming "
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
                    body=_("Purchase Order <b>%s</b> cancelled from Draft state.", order.name),
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
