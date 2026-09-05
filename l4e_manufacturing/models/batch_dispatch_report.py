# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class L4eBatchDispatchReport(models.Model):
    _name = "l4e.batch.dispatch.report"
    _description = "Batch Stock"
    _auto = False
    _order = "date desc, batch_id desc, id desc"

    batch_id = fields.Many2one("l4e.icecream.processing.batch", string="Batch Number", readonly=True)
    lot_id = fields.Many2one("l4e.icecream.processing.batch", string="Batch Number", readonly=True)
    batch_number = fields.Char(string="Batch Name", readonly=True)
    date = fields.Date(string="Batch Date", readonly=True)
    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    qty_produced = fields.Float(string="Produced Quantity", readonly=True)
    qty_sold = fields.Float(string="Quantity Sold", readonly=True)
    uom_id = fields.Many2one("uom.uom", string="UoM", readonly=True)
    batch_available_qty = fields.Float(string="Remaining Batch Stock", readonly=True)
    batch_status = fields.Selection(
        [
            ("in_stock", "In Stock"),
            ("finished", "Finished / Depleted"),
        ],
        string="Batch Stock Status",
        readonly=True,
    )
    company_id = fields.Many2one("res.company", string="Company", readonly=True)

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS l4e_batch_dispatch_report CASCADE;")
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW l4e_batch_dispatch_report AS (
                SELECT 
                    pb.id AS id,
                    pb.id AS batch_id,
                    pb.id AS lot_id,
                    pb.batch_number AS batch_number,
                    pb.date AS date,
                    pb.product_id AS product_id,
                    pb.total_output_qty AS qty_produced,
                    COALESCE(sales.total_sold, 0.0) AS qty_sold,
                    (
                        SELECT pt.uom_id 
                        FROM product_product pp 
                        JOIN product_template pt ON pt.id = pp.product_tmpl_id 
                        WHERE pp.id = pb.product_id 
                        LIMIT 1
                    ) AS uom_id,
                    GREATEST(pb.total_output_qty - COALESCE(sales.total_sold, 0.0), 0.0) AS batch_available_qty,
                    CASE
                        WHEN (pb.total_output_qty - COALESCE(sales.total_sold, 0.0)) > 0 THEN 'in_stock'
                        ELSE 'finished'
                    END AS batch_status,
                    pb.company_id AS company_id
                FROM l4e_icecream_processing_batch pb
                LEFT JOIN (
                    SELECT 
                        sol.batch_id,
                        SUM(sol.product_uom_qty) AS total_sold
                    FROM sale_order_line sol
                    JOIN sale_order so ON so.id = sol.order_id
                    WHERE so.state IN ('sale', 'done') AND sol.batch_id IS NOT NULL
                    GROUP BY sol.batch_id
                ) sales ON sales.batch_id = pb.id
                WHERE pb.state != 'cancel'
            )
        """)
