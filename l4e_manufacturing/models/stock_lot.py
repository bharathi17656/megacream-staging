# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class StockLot(models.Model):
    _inherit = "stock.lot"

    batch_id = fields.Many2one(
        "l4e.icecream.processing.batch",
        string="Manufacturing Processing Batch",
        index=True,
    )
