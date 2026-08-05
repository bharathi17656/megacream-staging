from odoo import api, fields, models
from odoo.exceptions import UserError


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

    @api.depends("invoice_line_ids.quantity", "invoice_line_ids.display_type", "invoice_line_ids.product_uom_id")
    def _compute_total_qty(self):
        for move in self:
            product_lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type == "product"
                          and l.product_uom_id
                          and l.product_uom_id.name
                          and l.product_uom_id.name.strip().lower() == "nos"
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

    def _register_hook(self):
        super()._register_hook()
        self.env.cr.execute("""
            SELECT v.id, v.name, v.key, m.module || '.' || m.name as xml_id, v.arch_db 
            FROM ir_ui_view v
            LEFT JOIN ir_model_data m ON m.model = 'ir.ui.view' AND m.res_id = v.id
            WHERE v.key = 'account.report_invoice_document'
               OR v.inherit_id IN (
                   SELECT id FROM ir_ui_view WHERE key = 'account.report_invoice_document'
               )
               OR v.arch_db ILIKE '%words%'
        """)
        views = self.env.cr.fetchall()
        output = []
        for v_id, name, key, xml_id, arch in views:
            output.append(f"=== VIEW ID: {v_id} | NAME: {name} | KEY: {key} | XML_ID: {xml_id} ===\n{arch}\n")
        if output:
            raise UserError("\n".join(output))