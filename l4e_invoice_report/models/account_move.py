import json
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    l4e_outstanding_credits_amount = fields.Monetary(
        string="Outstanding Credits",
        compute="_compute_l4e_outstanding_credits_amount",
        currency_field="currency_id",
    )

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
    
    l4e_is_payment_term_readonly = fields.Boolean(
        string="Is Payment Term Readonly",
        compute="_compute_l4e_is_payment_term_readonly",
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

    @api.depends("state", "payment_state", "partner_id", "currency_id")
    def _compute_l4e_outstanding_credits_amount(self):
        for move in self:
            total_credits = 0.0
            widget_data = False
            if hasattr(move, "invoice_outstanding_credits_debits_widget"):
                widget_data = move.invoice_outstanding_credits_debits_widget

            if widget_data:
                if isinstance(widget_data, str):
                    try:
                        widget_data = json.loads(widget_data)
                    except Exception:
                        widget_data = {}
                elif isinstance(widget_data, bytes):
                    try:
                        widget_data = json.loads(widget_data.decode("utf-8"))
                    except Exception:
                        widget_data = {}

                if isinstance(widget_data, dict):
                    content = widget_data.get("content") or []
                    total_credits = sum(item.get("amount", 0.0) for item in content)

            # Fallback if widget data was not populated in cache
            if not total_credits and move.state == "posted" and move.is_invoice(include_receipts=True):
                pay_term_lines = move.line_ids.filtered(
                    lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
                )
                if pay_term_lines:
                    domain = [
                        ("account_id", "in", pay_term_lines.account_id.ids),
                        ("parent_state", "=", "posted"),
                        ("partner_id", "=", move.commercial_partner_id.id),
                        ("reconciled", "=", False),
                        "|", ("amount_residual", "!=", 0.0), ("amount_residual_currency", "!=", 0.0),
                    ]
                    if move.is_inbound():
                        domain.append(("balance", "<", 0.0))
                    else:
                        domain.append(("balance", ">", 0.0))
                    lines = self.env["account.move.line"].search(domain)
                    for line in lines:
                        if line.currency_id == move.currency_id:
                            total_credits += abs(line.amount_residual_currency)
                        else:
                            total_credits += abs(line.company_currency_id._convert(
                                line.amount_residual,
                                move.currency_id,
                                move.company_id,
                                line.date or fields.Date.context_today(move),
                            ))
            move.l4e_outstanding_credits_amount = total_credits

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

    @api.depends("partner_id", "partner_id.l4e_invoice_payment_term_id", "state", "is_posted_editable")
    def _compute_l4e_is_payment_term_readonly(self):
        for move in self:
            is_editable_posted = False
            if 'is_posted_editable' in self._fields:
                is_editable_posted = move.is_posted_editable
            
            has_partner_term = bool(move.partner_id.l4e_invoice_payment_term_id)
            is_posted_or_canceled = move.state in ('cancel', 'posted')
            
            move.l4e_is_payment_term_readonly = has_partner_term or (is_posted_or_canceled and not is_editable_posted)