# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class L4eSaleOrderBatchAllocation(models.Model):
    _name = 'l4e.sale.order.batch.allocation'
    _description = 'Sale Order Line Batch Allocation'
    _order = 'batch_date asc, id asc'

    order_line_id = fields.Many2one(
        'sale.order.line',
        string='Sale Order Line',
        ondelete='cascade',
        required=True,
        index=True,
    )
    order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        related='order_line_id.order_id',
        store=True,
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        related='order_line_id.product_id',
        store=True,
        index=True,
    )
    batch_id = fields.Many2one(
        'l4e.icecream.processing.batch',
        string='Batch',
        required=True,
        index=True,
    )
    batch_number = fields.Char(
        string='Batch Number',
        related='batch_id.batch_number',
        store=True,
    )
    batch_date = fields.Date(
        string='Batch Date',
        related='batch_id.date',
        store=True,
    )
    quantity = fields.Float(
        string='Allocated Quantity',
        required=True,
        digits='Product Unit of Measure',
        default=0.0,
    )
