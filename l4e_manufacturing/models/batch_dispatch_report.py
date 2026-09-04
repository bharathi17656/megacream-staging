# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class L4eBatchDispatchReport(models.Model):
    _name = "l4e.batch.dispatch.report"
    _description = "Batch Dispatch & Sales Report"
    _auto = False
    _order = "date desc, id desc"

    batch_id = fields.Many2one("l4e.icecream.processing.batch", string="Batch Number", readonly=True)
    lot_id = fields.Many2one("l4e.icecream.processing.batch", string="Batch Number", readonly=True)
    batch_number = fields.Char(string="Batch Name", readonly=True)
    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Customer / Recipient", readonly=True)
    order_id = fields.Many2one("sale.order", string="Sales Order", readonly=True)
    order_ref = fields.Char(string="Order Reference", readonly=True)
    date = fields.Date(string="Sale Date", readonly=True)
    qty_sold = fields.Float(string="Quantity Sold", readonly=True)
    uom_id = fields.Many2one("uom.uom", string="UoM", readonly=True)
    price_unit = fields.Float(string="Unit Price", readonly=True)
    price_total = fields.Monetary(string="Total Amount", currency_field="currency_id", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Currency", readonly=True)
    batch_available_qty = fields.Float(string="Remaining Batch Stock", readonly=True)
    batch_status = fields.Selection(
        [
            ("in_stock", "In Stock"),
            ("finished", "Finished / Depleted"),
        ],
        string="Batch Status",
        readonly=True,
    )
    user_id = fields.Many2one("res.users", string="Salesperson", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS l4e_batch_dispatch_report CASCADE;")
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW l4e_batch_dispatch_report AS (
                SELECT 
                    sol.id AS id,
                    sol.batch_id AS batch_id,
                    sol.batch_id AS lot_id,
                    pb.batch_number AS batch_number,
                    sol.product_id AS product_id,
                    so.partner_id AS partner_id,
                    so.id AS order_id,
                    so.name AS order_ref,
                    so.date_order::date AS date,
                    sol.product_uom_qty AS qty_sold,
                    sol.product_uom_id AS uom_id,
                    sol.price_unit AS price_unit,
                    sol.price_subtotal AS price_total,
                    COALESCE(so.currency_id, comp.currency_id, (SELECT id FROM res_currency WHERE name = 'INR' LIMIT 1), 1) AS currency_id,
                    GREATEST(pb.total_output_qty - COALESCE(batch_sales.total_sold, 0.0), 0.0) AS batch_available_qty,
                    CASE
                        WHEN (pb.total_output_qty - COALESCE(batch_sales.total_sold, 0.0)) > 0 THEN 'in_stock'
                        ELSE 'finished'
                    END AS batch_status,
                    so.user_id AS user_id,
                    so.company_id AS company_id
                FROM sale_order_line sol
                JOIN sale_order so ON so.id = sol.order_id
                JOIN l4e_icecream_processing_batch pb ON pb.id = sol.batch_id
                LEFT JOIN (
                    SELECT 
                        sol2.batch_id,
                        SUM(sol2.product_uom_qty) AS total_sold
                    FROM sale_order_line sol2
                    JOIN sale_order so2 ON so2.id = sol2.order_id
                    WHERE so2.state IN ('sale', 'done') AND sol2.batch_id IS NOT NULL
                    GROUP BY sol2.batch_id
                ) batch_sales ON batch_sales.batch_id = pb.id
                LEFT JOIN res_company comp ON comp.id = so.company_id
                WHERE so.state IN ('sale', 'done') AND sol.batch_id IS NOT NULL
            )
        """)
