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
    
    l4e_partner_payment_term_id = fields.Many2one(
        related="partner_id.l4e_invoice_payment_term_id",
        string="Partner Invoice Payment Term",
        store=False,
    )
    
    salesperson_name = fields.Char(string="Salesperson Name")
    store_person_name = fields.Char(string="Store Person Name")
    store_person_number = fields.Char(string="Store Person Number")
    accounts_name = fields.Char(string="Accounts Name")
    
    def _l4e_default_invoice_date(self):
        if self.env.context.get("default_move_type") in ("in_invoice", "in_refund"):
            return fields.Date.context_today(self)
        return False

    invoice_date = fields.Date(default=_l4e_default_invoice_date)

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

    @api.depends("invoice_line_ids.sale_line_ids.order_id.user_id")
    def _compute_l4e_salesperson_info(self):
        for move in self:
            salesperson = move.l4e_sale_order_id.user_id
            move.l4e_salesperson_name = salesperson.name or False
            move.l4e_salesperson_contact = salesperson.partner_id.phone or False

    @api.depends("partner_id", "partner_id.l4e_invoice_payment_term_id")
    def _compute_invoice_payment_term_id(self):
        super()._compute_invoice_payment_term_id()
        for move in self:
            if move.is_sale_document(include_receipts=True) and move.partner_id.l4e_invoice_payment_term_id:
                move.invoice_payment_term_id = move.partner_id.l4e_invoice_payment_term_id

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            if (
                move.is_sale_document(include_receipts=True)
                and move.partner_id.l4e_invoice_payment_term_id
                and move.invoice_payment_term_id != move.partner_id.l4e_invoice_payment_term_id
            ):
                move.invoice_payment_term_id = move.partner_id.l4e_invoice_payment_term_id
        return moves