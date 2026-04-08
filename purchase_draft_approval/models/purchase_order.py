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
        # required=False
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

    # Track whether current user has store_indent enabled
    user_has_store_indent = fields.Boolean(
        string='User Has Store Indent',
        compute='_compute_user_has_store_indent',
    )

    # -------------------------------------------------------
    # Compute
    # -------------------------------------------------------
    @api.depends('state')
    def _compute_user_has_store_indent(self):
        for order in self:
            order.user_has_store_indent = self.env.user.store_indent

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
    # Constraint: vendor required only if NOT store_indent user
    # -------------------------------------------------------
    # @api.constrains('state', 'partner_id')
    # def _check_vendor_required(self):
    #     for order in self:
    #         if order.state == 'draft_indent':
    #             # Store indent users don't need a vendor in draft
    #             if not order.user_has_store_indent and not order.partner_id:
    #                 # We only warn at button action time, not on every save
    #                 pass

    # -------------------------------------------------------
    # Button: Request RFQ Approval (sends approval request)
    # -------------------------------------------------------
    def button_request_rfq_approval(self):
        """
        Called when the user clicks 'Send to RFQ' in Draft state.
        Validates required fields, then sends an approval request
        to the Procurement Manager (Purchase Administrator) group.
        """
        self.ensure_one()

        if self.state != 'draft_indent':
            raise UserError(_("Only orders in Draft state can be sent for RFQ approval."))

        # Vendor is mandatory for non-store-indent users
        if not self.env.user.store_indent and not self.partner_id:
            raise ValidationError(
                _("Please set a Vendor before requesting RFQ approval.")
            )

        # Check if there are any order lines
        if not self.order_line:
            raise ValidationError(
                _("Please add at least one product line before requesting RFQ approval.")
            )

        # Find Procurement Manager / Purchase Administrator group
        purchase_admin_group = self.env.ref(
            'purchase.group_purchase_manager', raise_if_not_found=False
        )
        managers = self.env['res.users']
        if purchase_admin_group:
            managers = purchase_admin_group.user_ids.filtered(lambda u: u.active)

        if not managers:
            raise UserError(
                _("No Procurement Manager found. Please assign users to the "
                  "'Purchase / Administrator' group.")
            )

        # Set approval state to pending
        self.write({
            'approval_state': 'pending',
        })

        # Post a message and notify procurement managers
        partner_ids = managers.mapped('partner_id').ids
        self.message_post(
            body=_(
                "%(user)s has requested approval to move Purchase Order "
                "<b>%(name)s</b> from <b>Draft</b> to <b>RFQ</b> state. "
                "Please review and approve or refuse.",
                user=self.env.user.name,
                name=self.name,
            ),
            subject=_("RFQ Approval Request: %s", self.name),
            partner_ids=partner_ids,
            subtype_xmlid='mail.mt_comment',
        )

        # Schedule activity for each procurement manager
        activity_type = self.env.ref(
            'purchase_draft_approval.mail_activity_rfq_approval',
            raise_if_not_found=False,
        )
        activity_type_id = activity_type.id if activity_type else self.env.ref(
            'mail.mail_activity_data_todo'
        ).id

        for manager in managers:
            self.activity_schedule(
                activity_type_id=activity_type_id,
                summary=_("RFQ Approval Required: %s", self.name),
                note=_(
                    "Purchase Order %(name)s is waiting for your approval "
                    "to move to RFQ state. Created by: %(user)s",
                    name=self.name,
                    user=self.env.user.name,
                ),
                user_id=manager.id,
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Approval Requested"),
                'message': _(
                    "Your request to move %s to RFQ has been sent to "
                    "Procurement Managers for approval.", self.name
                ),
                'type': 'success',
                'sticky': False,
            }
        }

    # -------------------------------------------------------
    # Button: Approve RFQ (only for Purchase Admins)
    # -------------------------------------------------------
    def button_approve_rfq(self):
        """
        Procurement Manager approves the RFQ request.
        Moves the order from draft_indent -> draft (RFQ state).
        """
        self.ensure_one()

        # Only Purchase Admins / Procurement Managers can approve
        if not self.env.user.has_group('purchase.group_purchase_manager'):
            raise UserError(
                _("Only Procurement Managers can approve RFQ requests.")
            )

        if self.state != 'draft_indent':
            raise UserError(_("Only Draft orders can be approved for RFQ."))

        if self.approval_state != 'pending':
            raise UserError(_("This order does not have a pending approval request."))

        # Mark activities as done
        self.activity_ids.filtered(
            lambda a: a.user_id == self.env.user
        ).action_feedback(
            feedback=_("RFQ Approved by %s", self.env.user.name)
        )

        self.write({
            'state': 'draft',          # Standard Odoo RFQ state
            'approval_state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now(),
        })

        self.message_post(
            body=_(
                "<b>RFQ Approved</b> by %(manager)s. "
                "Purchase Order <b>%(name)s</b> has moved to <b>RFQ</b> state.",
                manager=self.env.user.name,
                name=self.name,
            ),
            subtype_xmlid='mail.mt_comment',
        )

    # -------------------------------------------------------
    # Button: Refuse RFQ (only for Purchase Admins)
    # -------------------------------------------------------
    def button_refuse_rfq(self):
        """
        Procurement Manager refuses the RFQ request.
        Order stays in draft_indent state.
        """
        self.ensure_one()

        if not self.env.user.has_group('purchase.group_purchase_manager'):
            raise UserError(
                _("Only Procurement Managers can refuse RFQ requests.")
            )

        if self.approval_state != 'pending':
            raise UserError(_("This order does not have a pending approval request."))

        # Mark activities as done
        self.activity_ids.filtered(
            lambda a: a.user_id == self.env.user
        ).action_feedback(
            feedback=_("RFQ Refused by %s", self.env.user.name)
        )

        self.write({
            'approval_state': 'refused',
        })

        self.message_post(
            body=_(
                "<b>RFQ Refused</b> by %(manager)s. "
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
    # Override: prevent 'Confirm Order' from draft_indent
    # -------------------------------------------------------
    def button_confirm(self):
        for order in self:
            if order.state == 'draft_indent':
                raise UserError(
                    _("Please request RFQ approval first before confirming "
                      "Purchase Order %s.", order.name)
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
