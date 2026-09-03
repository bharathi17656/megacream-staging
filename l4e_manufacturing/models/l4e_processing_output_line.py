# -*- coding: utf-8 -*-

from odoo import api, fields, models


class L4eIceCreamOutputLine(models.Model):
    _name = "l4e.icecream.output.line"
    _description = "Ice Cream Processing Output Line"

    batch_id = fields.Many2one(
        "l4e.icecream.processing.batch",
        string="Processing Batch",
        required=True,
        ondelete="cascade",
        index=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Finished Product",
        required=True,
        domain="[('type', 'in', ['product', 'consu'])]",
    )

    lot_id = fields.Many2one(
        "stock.lot",
        string="Output Lot / Batch No",
        domain="[('product_id', '=', product_id)]",
    )

    packaging_no = fields.Char(
        string="Packaging / Tub No",
        help="Tub number, crate number, or packaging reference",
    )

    quantity = fields.Float(
        string="Quantity Produced",
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

    unit_price = fields.Float(
        string="Unit Price / Value",
        compute="_compute_unit_price",
        store=True,
        readonly=False,
        digits="Product Price",
    )

    total_value = fields.Float(
        string="Total Value",
        compute="_compute_total_value",
        store=True,
        digits="Product Price",
    )

    remarks = fields.Char(string="Remarks")

    @api.depends("product_id", "product_id.list_price", "product_id.standard_price")
    def _compute_unit_price(self):
        for line in self:
            if line.product_id:
                line.unit_price = line.product_id.list_price or line.product_id.standard_price or 0.0
            else:
                line.unit_price = 0.0

    @api.depends("quantity", "unit_price")
    def _compute_total_value(self):
        for line in self:
            line.total_value = (line.quantity or 0.0) * (line.unit_price or 0.0)