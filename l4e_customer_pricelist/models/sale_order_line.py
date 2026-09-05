# -*- coding: utf-8 -*-

from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _compute_price_unit(self):
        super()._compute_price_unit()
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
