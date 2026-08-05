from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    total_qty = fields.Float(
        string="Total Quantity",
        compute="_compute_total_qty",
    )

    l4e_sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Source Sale Order",
        compute="_compute_l4e_sale_order_id",
    )

    l4e_salesperson_name = fields.Char(
        string="Sales Person",
        compute="_compute_l4e_salesperson_info",
    )

    l4e_salesperson_contact = fields.Char(
        string="Sales Person Contact",
        compute="_compute_l4e_salesperson_info",
    )

    @api.depends("invoice_line_ids.quantity", "invoice_line_ids.display_type")
    def _compute_total_qty(self):
        for move in self:
            product_lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type == "product"
            )
            move.total_qty = sum(product_lines.mapped("quantity"))

    @api.depends("invoice_line_ids.sale_line_ids.order_id")
    def _compute_l4e_sale_order_id(self):
        for move in self:
            orders = move.invoice_line_ids.sale_line_ids.order_id
            move.l4e_sale_order_id = orders[:1]

    @api.depends("l4e_sale_order_id.user_id")
    def _compute_l4e_salesperson_info(self):
        for move in self:
            salesperson = move.l4e_sale_order_id.user_id
            move.l4e_salesperson_name = salesperson.name or False
            move.l4e_salesperson_contact = salesperson.partner_id.phone or False