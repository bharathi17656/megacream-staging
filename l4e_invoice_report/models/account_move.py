from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    total_qty = fields.Float(
        string="Total Quantity",
        compute="_compute_total_qty",
    )

    @api.depends("invoice_line_ids.quantity", "invoice_line_ids.display_type")
    def _compute_total_qty(self):
        for move in self:
            product_lines = move.invoice_line_ids.filtered(
                lambda l: not l.display_type
            )
            move.total_qty = sum(product_lines.mapped("quantity"))
