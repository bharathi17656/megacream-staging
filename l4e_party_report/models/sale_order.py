# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_party_order = fields.Boolean(
        string="Party Order / Fridge Issued",
        default=False,
        copy=False,
        tracking=True,
        help="Check this box if ice cream is supplied for a party/event with company refrigerator(s).",
    )

    fridge_qty_dispatched = fields.Integer(
        string="Fridges Dispatched",
        default=0,
        copy=False,
        tracking=True,
        help="Total number of portable refrigerators / freezers dispatched to the customer for this order.",
    )

    fridge_qty_returned = fields.Integer(
        string="Fridges Returned",
        default=0,
        copy=False,
        tracking=True,
        help="Total number of refrigerators returned back by the customer.",
    )

    fridge_qty_missing = fields.Integer(
        string="Missing / Pending Fridges",
        compute="_compute_fridge_status",
        store=True,
        tracking=True,
        help="Number of refrigerators still held by the customer (Dispatched - Returned).",
    )

    fridge_serial_no = fields.Char(
        string="Fridge / Tag No",
        copy=False,
        tracking=True,
        help="Serial numbers, asset tags, or identifiers of the dispatched refrigerator(s).",
    )

    fridge_expected_return_date = fields.Date(
        string="Expected Return Date",
        copy=False,
        tracking=True,
        help="Expected date by which the customer should return the refrigerator(s).",
    )

    fridge_actual_return_date = fields.Date(
        string="Actual Return Date",
        copy=False,
        tracking=True,
        help="Date when the last refrigerator was returned.",
    )

    fridge_return_status = fields.Selection(
        [
            ("not_issued", "Not Issued"),
            ("pending", "Missing / Pending Return"),
            ("partial", "Partially Returned"),
            ("returned", "Fully Returned"),
        ],
        string="Fridge Status",
        compute="_compute_fridge_status",
        store=True,
        default="not_issued",
        tracking=True,
    )

    is_fridge_overdue = fields.Boolean(
        string="Overdue Return",
        compute="_compute_fridge_overdue",
        help="True if expected return date is past and fridges are still missing.",
    )

    partner_phone = fields.Char(
        related="partner_id.phone",
        string="Customer Phone",
        readonly=True,
    )

    partner_email = fields.Char(
        related="partner_id.email",
        string="Customer Email",
        readonly=True,
    )

    fridge_notes = fields.Text(
        string="Party & Fridge Remarks",
        copy=False,
        help="Party venue, contact person at event, follow-up remarks, or return notes.",
    )

    @api.depends("is_party_order", "fridge_qty_dispatched", "fridge_qty_returned")
    def _compute_fridge_status(self):
        for order in self:
            if not order.is_party_order or order.fridge_qty_dispatched <= 0:
                order.fridge_qty_missing = 0
                order.fridge_return_status = "not_issued"
            else:
                missing = max(0, order.fridge_qty_dispatched - order.fridge_qty_returned)
                order.fridge_qty_missing = missing
                if order.fridge_qty_returned <= 0:
                    order.fridge_return_status = "pending"
                elif order.fridge_qty_returned < order.fridge_qty_dispatched:
                    order.fridge_return_status = "partial"
                else:
                    order.fridge_return_status = "returned"

    def _compute_fridge_overdue(self):
        today = fields.Date.context_today(self)
        for order in self:
            if (
                order.is_party_order
                and order.fridge_qty_missing > 0
                and order.fridge_expected_return_date
                and order.fridge_expected_return_date < today
            ):
                order.is_fridge_overdue = True
            else:
                order.is_fridge_overdue = False

    @api.constrains("fridge_qty_dispatched", "fridge_qty_returned")
    def _check_fridge_quantities(self):
        for order in self:
            if order.fridge_qty_dispatched < 0:
                raise ValidationError(_("Dispatched refrigerator quantity cannot be negative."))
            if order.fridge_qty_returned < 0:
                raise ValidationError(_("Returned refrigerator quantity cannot be negative."))
            if order.fridge_qty_returned > order.fridge_qty_dispatched and order.fridge_qty_dispatched > 0:
                raise ValidationError(
                    _(
                        "Returned refrigerator quantity (%s) cannot exceed dispatched quantity (%s)."
                    )
                    % (order.fridge_qty_returned, order.fridge_qty_dispatched)
                )

    def action_open_fridge_return_wizard(self):
        """Open popup wizard to quickly log returned refrigerator(s)."""
        self.ensure_one()
        return {
            "name": _("Log Refrigerator Return"),
            "type": "ir.actions.act_window",
            "res_model": "fridge.return.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_sale_order_id": self.id,
                "default_qty_to_return": self.fridge_qty_missing,
                "default_return_date": fields.Date.context_today(self),
            },
        }
