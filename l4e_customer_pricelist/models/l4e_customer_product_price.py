# -*- coding: utf-8 -*-

from odoo import api, fields, models


class L4eCustomerProductPrice(models.Model):
    _name = "l4e.customer.product.price"
    _description = "Customer Specific Product Price"
    _order = "sequence, id"

    sequence = fields.Integer(string="S.No", default=1)
    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True, ondelete="cascade", index=True
    )
    product_id = fields.Many2one("product.product", string="Product", required=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="partner_id.company_id.currency_id",
        readonly=True,
    )
    actual_price = fields.Float(
        string="Actual Price",
        related="product_id.lst_price",
        readonly=True,
        help="Product's current Sales Price from Inventory/Sales. Not editable here.",
    )
    customer_price = fields.Float(
        string="Customer Price",
        help="Price to apply for this product when this customer orders it.",
    )

    _sql_constraints = [
        (
            "partner_product_uniq",
            "unique(partner_id, product_id)",
            "A price for this product is already defined for this customer.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("sequence") and vals.get("partner_id"):
                last = self.search(
                    [("partner_id", "=", vals["partner_id"])], order="sequence desc", limit=1
                )
                vals["sequence"] = (last.sequence or 0) + 1
        return super().create(vals_list)
