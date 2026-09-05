# -*- coding: utf-8 -*-

from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.onchange("product_id")
    def _onchange_product_id_l4e_customer_price(self):
        self._apply_l4e_customer_price()

    def _compute_price_unit(self):
        super()._compute_price_unit()
        self._apply_l4e_customer_price()

    def _apply_l4e_customer_price(self):
        for line in self:
            partner = line.order_id.partner_id
            if not line.product_id or not partner:
                continue
            custom_price = self.env["l4e.customer.product.price"].search(
                [
                    ("partner_id", "=", partner.id),
                    ("product_id", "=", line.product_id.id),
                ],
                limit=1,
            )
            if custom_price:
                line.price_unit = custom_price.customer_price

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._apply_l4e_customer_price()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if "product_id" in vals or "order_id" in vals:
            self._apply_l4e_customer_price()
        return res