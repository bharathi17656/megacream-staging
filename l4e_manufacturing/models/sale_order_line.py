# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    batch_id = fields.Many2one(
        "l4e.icecream.processing.batch",
        string="Batch Number",
        domain="['|', ('product_id', '=', product_id), ('output_line_ids.product_id', '=', product_id)]",
        context="{'hide_depleted_batches': True}",
        help="Select the manufacturing processing batch issued to the customer.",
    )

    lot_id = fields.Many2one(
        "stock.lot",
        string="Stock Lot",
    )

    batch_available_qty = fields.Float(
        string="Batch Avail. Qty",
        related="batch_id.qty_available",
        readonly=True,
    )

    batch_status = fields.Selection(
        string="Batch Status",
        related="batch_id.batch_stock_status",
        readonly=True,
    )

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        if self.batch_id:
            res["batch_id"] = self.batch_id.id
        return res
