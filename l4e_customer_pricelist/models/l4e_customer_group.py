# -*- coding: utf-8 -*-

from odoo import api, fields, models


class L4eCustomerGroup(models.Model):
    _name = "l4e.customer.group"
    _description = "Customer Price Group"

    name = fields.Char(string="Group Name", required=True)
    customer_ids = fields.Many2many(
        "res.partner",
        string="Customers",
        domain=[("is_customer", "=", True)],
    )
    price_line_ids = fields.One2many(
        "l4e.customer.group.price", "group_id", string="Group Product Prices"
    )
    customer_count = fields.Integer(string="Customers", compute="_compute_customer_count")

    @api.depends("customer_ids")
    def _compute_customer_count(self):
        for group in self:
            group.customer_count = len(group.customer_ids)


class L4eCustomerGroupPrice(models.Model):
    _name = "l4e.customer.group.price"
    _description = "Customer Group Product Price"
    _order = "sequence, id"

    sequence = fields.Integer(string="S.No", default=1)
    group_id = fields.Many2one(
        "l4e.customer.group",
        string="Customer Group",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one("product.product", string="Product", required=True)
    actual_price = fields.Float(
        string="Actual Price",
        related="product_id.lst_price",
        readonly=True,
        help="Product's current Sales Price from Inventory/Sales. Not editable here.",
    )
    group_price = fields.Float(
        string="Group Price",
        help="Price to apply when a customer belonging to this group orders this product.",
    )

    _sql_constraints = [
        (
            "group_product_uniq",
            "unique(group_id, product_id)",
            "A price for this product is already defined for this group.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("sequence") and vals.get("group_id"):
                last = self.search(
                    [("group_id", "=", vals["group_id"])], order="sequence desc", limit=1
                )
                vals["sequence"] = (last.sequence or 0) + 1
        return super().create(vals_list)
