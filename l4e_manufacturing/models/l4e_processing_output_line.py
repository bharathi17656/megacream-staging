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

    wastage_quantity = fields.Float(
        string="Wastage Qty",
        compute="_compute_wastage_and_net_qty",
        store=True,
        digits="Product Unit of Measure",
    )

    net_quantity = fields.Float(
        string="Net FG Qty",
        compute="_compute_wastage_and_net_qty",
        store=True,
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

    @api.depends("quantity", "batch_id.wastage_line_ids.quantity", "batch_id.wastage_line_ids.product_id")
    def _compute_wastage_and_net_qty(self):
        for line in self:
            if not line.batch_id or not line.product_id:
                line.wastage_quantity = 0.0
                line.net_quantity = line.quantity
                continue
            matching_wastage = sum(
                w.quantity for w in line.batch_id.wastage_line_ids if w.product_id == line.product_id
            )
            same_prod_lines = line.batch_id.output_line_ids.filtered(lambda l: l.product_id == line.product_id)
            if len(same_prod_lines) > 1:
                total_prod_qty = sum(same_prod_lines.mapped("quantity"))
                ratio = (line.quantity / total_prod_qty) if total_prod_qty > 0 else 0.0
                line.wastage_quantity = matching_wastage * ratio
            else:
                line.wastage_quantity = matching_wastage
            line.net_quantity = max(0.0, line.quantity - line.wastage_quantity)

    @api.depends("product_id", "product_id.list_price", "product_id.standard_price")
    def _compute_unit_price(self):
        for line in self:
            if line.product_id:
                line.unit_price = line.product_id.list_price or line.product_id.standard_price or 0.0
            else:
                line.unit_price = 0.0

    @api.depends("net_quantity", "quantity", "unit_price")
    def _compute_total_value(self):
        for line in self:
            qty = line.net_quantity if line.net_quantity is not False else line.quantity
            line.total_value = (qty or 0.0) * (line.unit_price or 0.0)