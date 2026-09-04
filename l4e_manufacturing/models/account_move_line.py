# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    batch_id = fields.Many2one(
        "l4e.icecream.processing.batch",
        string="Batch Number",
        domain="['&', '|', ('product_id', '=', product_id), ('output_line_ids.product_id', '=', product_id), ('batch_stock_status', '=', 'in_stock')]",
        help="Select the manufacturing processing batch associated with this invoice line.",
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
