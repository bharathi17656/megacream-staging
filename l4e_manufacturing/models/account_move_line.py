# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    batch_id = fields.Many2one(
        "l4e.icecream.processing.batch",
        string="Batch Number",
        domain="['|', ('product_id', '=', product_id), ('output_line_ids.product_id', '=', product_id)]",
        context="{'hide_depleted_batches': True, 'filter_product_id': product_id}",
        help="Select the manufacturing processing batch associated with this invoice line.",
    )

    lot_id = fields.Many2one(
        "stock.lot",
        string="Stock Lot",
    )

    batch_available_qty = fields.Float(
        string="Batch Avail. Qty",
        compute="_compute_batch_product_stock",
        readonly=True,
    )

    batch_status = fields.Selection(
        [
            ("in_stock", "In Stock"),
            ("finished", "Finished / Depleted"),
        ],
        string="Batch Status",
        compute="_compute_batch_product_stock",
        readonly=True,
    )

    @api.depends("batch_id", "product_id")
    def _compute_batch_product_stock(self):
        for line in self:
            if not line.batch_id or not line.product_id:
                line.batch_available_qty = 0.0
                line.batch_status = False
                continue
            output_lines = line.batch_id.output_line_ids.filtered(lambda ol: ol.product_id == line.product_id)
            if output_lines:
                prod_qty = sum(output_lines.mapped("quantity"))
            elif line.batch_id.product_id == line.product_id:
                prod_qty = line.batch_id.total_output_qty
            else:
                prod_qty = 0.0

            sold_lines = self.env["sale.order.line"].sudo().search([
                ("batch_id", "=", line.batch_id.id),
                ("product_id", "=", line.product_id.id),
                ("order_id.state", "in", ("sale", "done")),
            ])
            sold_qty = sum(sold_lines.mapped("product_uom_qty"))
            avail = prod_qty - sold_qty
            line.batch_available_qty = max(avail, 0.0)
            line.batch_status = "in_stock" if avail > 0 else "finished"
