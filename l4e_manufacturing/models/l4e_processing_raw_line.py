# -*- coding: utf-8 -*-

from odoo import api, fields, models


class L4eIceCreamRawLine(models.Model):
    _name = "l4e.icecream.raw.line"
    _description = "Ice Cream Processing Raw Material Line"

    batch_id = fields.Many2one(
        "l4e.icecream.processing.batch",
        string="Processing Batch",
        required=True,
        ondelete="cascade",
        index=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Raw Material Ingredient",
        required=True,
        domain="[('type', 'in', ['product', 'consu'])]",
    )

    raw_lot_ids = fields.Many2many(
        "stock.lot",
        "l4e_icecream_raw_line_lot_rel",
        "raw_line_id",
        "lot_id",
        string="Ingredient Lots",
        domain="[('product_id', '=', product_id)]",
    )

    quantity = fields.Float(
        string="Quantity Required",
        required=True,
        default=1.0,
        digits="Product Unit of Measure",
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="UoM",
        related="product_id.uom_id",
        readonly=True,
        store=True,
    )

    unit_cost = fields.Float(
        string="Unit Cost",
        related="product_id.standard_price",
        readonly=True,
        digits="Product Price",
    )

    total_cost = fields.Float(
        string="Total Cost",
        compute="_compute_total_cost",
        store=True,
        digits="Product Price",
    )

    @api.depends("quantity", "product_id", "product_id.standard_price")
    def _compute_total_cost(self):
        for line in self:
            cost = line.product_id.standard_price or 0.0
            line.total_cost = line.quantity * cost