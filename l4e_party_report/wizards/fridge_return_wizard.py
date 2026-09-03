# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FridgeReturnWizard(models.TransientModel):
    _name = "fridge.return.wizard"
    _description = "Log Refrigerator Return Wizard"

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Sale Order",
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        related="sale_order_id.partner_id",
        readonly=True,
    )
    fridge_qty_dispatched = fields.Integer(
        string="Total Dispatched",
        related="sale_order_id.fridge_qty_dispatched",
        readonly=True,
    )
    already_returned = fields.Integer(
        string="Already Returned",
        related="sale_order_id.fridge_qty_returned",
        readonly=True,
    )
    current_missing = fields.Integer(
        string="Currently Missing / Pending",
        related="sale_order_id.fridge_qty_missing",
        readonly=True,
    )
    qty_to_return = fields.Integer(
        string="Quantity Returning Now",
        required=True,
        default=1,
        help="Number of refrigerators returning now.",
    )
    return_date = fields.Date(
        string="Return Date",
        required=True,
        default=fields.Date.context_today,
    )
    return_notes = fields.Text(
        string="Return Notes / Condition",
        help="Condition of the refrigerator upon return, damage notes, etc.",
    )

    @api.constrains("qty_to_return")
    def _check_qty_to_return(self):
        for wiz in self:
            if wiz.qty_to_return <= 0:
                raise ValidationError(_("Quantity returning must be at least 1."))
            if wiz.qty_to_return > wiz.current_missing:
                raise ValidationError(
                    _(
                        "Quantity returning (%s) cannot be greater than the currently missing quantity (%s)."
                    )
                    % (wiz.qty_to_return, wiz.current_missing)
                )

    def action_confirm_return(self):
        self.ensure_one()
        order = self.sale_order_id
        new_returned_qty = order.fridge_qty_returned + self.qty_to_return
        
        note_msg = _("\n[%s] Logged return of %s refrigerator(s).") % (
            self.return_date,
            self.qty_to_return,
        )
        if self.return_notes:
            note_msg += _(" Note: %s") % self.return_notes

        existing_notes = order.fridge_notes or ""
        order.write({
            "fridge_qty_returned": new_returned_qty,
            "fridge_actual_return_date": self.return_date,
            "fridge_notes": (existing_notes + note_msg).strip(),
        })

        order.message_post(
            body=_(
                "<b>Refrigerator Return Logged:</b><br/>"
                "- Quantity Returned: %s<br/>"
                "- Total Returned: %s / %s<br/>"
                "- Remaining Missing: %s<br/>"
                "- Return Date: %s"
            )
            % (
                self.qty_to_return,
                new_returned_qty,
                order.fridge_qty_dispatched,
                order.fridge_qty_missing,
                self.return_date,
            )
        )
        return {"type": "ir.actions.act_window_close"}
