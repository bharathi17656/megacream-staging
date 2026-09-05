# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    customer_product_price_ids = fields.One2many(
        "l4e.customer.product.price",
        "partner_id",
        string="Customer Product Prices",
    )
