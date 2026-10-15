# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class L4eIceCreamProcessingBatch(models.Model):
    _name = "l4e.icecream.processing.batch"
    _description = "Ice Cream Processing Batch"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _rec_name = "batch_number"

    # Processing Order Reference (e.g. MC2026-00001)
    name = fields.Char(
        string="Order Reference",
        required=True,
        copy=False,
        default="New",
        tracking=True,
    )

    date = fields.Date(
        string="Requested Date",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )

    # Daily Resetting Batch Number: BATCH-DD-MMM-YY-001 (e.g. BATCH-01-AUG-26-001)
    batch_number = fields.Char(
        string="Batch Number",
        required=True,
        copy=False,
        default=lambda self: self._get_default_batch_number(),
        tracking=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("at_store", "At Store"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
        copy=False,
        tracking=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )

    is_sales_user = fields.Boolean(
        string="Is Sales User",
        compute="_compute_is_sales_user",
    )
    is_store_user = fields.Boolean(
        string="Is Store User",
        compute="_compute_user_roles",
    )
    is_production_user = fields.Boolean(
        string="Is Production User",
        compute="_compute_user_roles",
    )

    @api.depends_context("uid")
    def _compute_is_sales_user(self):
        user = self.env.user
        is_sales = bool(
            getattr(user, "is_sales_user", False)
            or (
                user.has_group("sales_team.group_sale_salesman")
                and not user.has_group("mrp.group_mrp_user")
                and not user.has_group("stock.group_stock_user")
                and not user.has_group("base.group_system")
            )
        )
        for record in self:
            record.is_sales_user = is_sales

    @api.depends_context("uid")
    def _compute_user_roles(self):
        user = self.env.user
        is_admin = user._is_admin() or user.has_group("base.group_system")
        is_store = bool(
            getattr(user, "is_store_user", False)
            or user.has_group("stock.group_stock_user")
            or is_admin
        )
        is_prod = bool(
            getattr(user, "is_production_user", False)
            or user.has_group("mrp.group_mrp_user")
            or is_admin
        )
        for record in self:
            record.is_store_user = is_store
            record.is_production_user = is_prod

    is_store_confirmed = fields.Boolean(
        string="Store Confirmed",
        default=False,
        copy=False,
        tracking=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Finished Product",
        compute="_compute_product_id",
        store=True,
    )

    raw_product_id = fields.Many2one(
        "product.product",
        string="Primary Raw Material",
        compute="_compute_raw_product_id",
        store=True,
    )

    @api.depends("output_line_ids.product_id")
    def _compute_product_id(self):
        for rec in self:
            rec.product_id = rec.output_line_ids[0].product_id if rec.output_line_ids else False

    @api.depends("raw_line_ids.product_id")
    def _compute_raw_product_id(self):
        for rec in self:
            rec.raw_product_id = rec.raw_line_ids[0].product_id if rec.raw_line_ids else False

    qty_sold = fields.Float(
        string="Quantity Sold",
        compute="_compute_qty_sold_available",
    )
    qty_available = fields.Float(
        string="Available Quantity",
        compute="_compute_qty_sold_available",
        search="_search_qty_available",
    )
    batch_available_qty = fields.Float(
        string="Available Quantity",
        compute="_compute_qty_sold_available",
    )
    batch_stock_status = fields.Selection(
        [
            ("in_stock", "In Stock"),
            ("finished", "Finished / Depleted"),
        ],
        string="Stock Status",
        compute="_compute_qty_sold_available",
        search="_search_batch_stock_status",
    )

    def _compute_qty_sold_available(self):
        filter_product_id = self.env.context.get("filter_product_id")
        for rec in self:
            prod_id = filter_product_id or (rec.product_id.id if rec.product_id else False)
            if prod_id:
                matching_output = rec.output_line_ids.filtered(lambda ol: ol.product_id.id == prod_id)
                if matching_output:
                    prod_qty = sum(matching_output.mapped("net_quantity"))
                elif rec.product_id.id == prod_id:
                    prod_qty = rec.total_net_output_qty
                else:
                    prod_qty = 0.0

                sold_allocs = self.env["l4e.sale.order.batch.allocation"].sudo().search([
                    ("batch_id", "=", rec.id),
                    ("product_id", "=", prod_id),
                    ("order_id.state", "in", ("sale", "done")),
                ])
                sold_from_allocs = sum(sold_allocs.mapped("quantity"))

                sold_lines = self.env["sale.order.line"].sudo().search([
                    ("batch_id", "=", rec.id),
                    ("product_id", "=", prod_id),
                    ("order_id.state", "in", ("sale", "done")),
                    ("batch_allocation_ids", "=", False),
                ])
                total_sold = sold_from_allocs + sum(sold_lines.mapped("product_uom_qty"))
                rec.qty_sold = total_sold
                avail = prod_qty - total_sold
                rec.qty_available = max(avail, 0.0)
                rec.batch_available_qty = max(avail, 0.0)
                rec.batch_stock_status = "in_stock" if avail > 0 else "finished"
            else:
                sold_allocs = self.env["l4e.sale.order.batch.allocation"].sudo().search([
                    ("batch_id", "=", rec.id),
                    ("order_id.state", "in", ("sale", "done")),
                ])
                sold_from_allocs = sum(sold_allocs.mapped("quantity"))

                sold_lines = self.env["sale.order.line"].sudo().search([
                    ("batch_id", "=", rec.id),
                    ("order_id.state", "in", ("sale", "done")),
                    ("batch_allocation_ids", "=", False),
                ])
                total_sold = sold_from_allocs + sum(sold_lines.mapped("product_uom_qty"))
                rec.qty_sold = total_sold
                avail = rec.total_net_output_qty - total_sold
                rec.qty_available = max(avail, 0.0)
                rec.batch_available_qty = max(avail, 0.0)
                rec.batch_stock_status = "in_stock" if avail > 0 else "finished"

    def _search_batch_stock_status(self, operator, value):
        if operator in ("=", "!="):
            self.env.cr.execute("""
                SELECT pb.id
                FROM l4e_icecream_processing_batch pb
                LEFT JOIN (
                    SELECT b_id AS batch_id, SUM(s_qty) AS total_sold
                    FROM (
                        SELECT ba.batch_id AS b_id, ba.quantity AS s_qty
                        FROM l4e_sale_order_batch_allocation ba
                        JOIN sale_order so ON so.id = ba.order_id
                        WHERE so.state IN ('sale', 'done')
                        UNION ALL
                        SELECT sol.batch_id AS b_id, sol.product_uom_qty AS s_qty
                        FROM sale_order_line sol
                        JOIN sale_order so ON so.id = sol.order_id
                        WHERE so.state IN ('sale', 'done') AND sol.batch_id IS NOT NULL
                          AND NOT EXISTS (
                              SELECT 1 FROM l4e_sale_order_batch_allocation ba WHERE ba.order_line_id = sol.id
                          )
                    ) sub_sales
                    GROUP BY b_id
                ) sales ON sales.batch_id = pb.id
                WHERE (pb.total_net_output_qty - COALESCE(sales.total_sold, 0.0)) > 0
            """)
            in_stock_ids = [row[0] for row in self.env.cr.fetchall()]
            if (operator == "=" and value == "in_stock") or (operator == "!=" and value == "finished"):
                return [("id", "in", in_stock_ids)]
            else:
                return [("id", "not in", in_stock_ids)]
        return []

    def _search_qty_available(self, operator, value):
        self.env.cr.execute("""
            SELECT pb.id
            FROM l4e_icecream_processing_batch pb
            LEFT JOIN (
                SELECT b_id AS batch_id, SUM(s_qty) AS total_sold
                FROM (
                    SELECT ba.batch_id AS b_id, ba.quantity AS s_qty
                    FROM l4e_sale_order_batch_allocation ba
                    JOIN sale_order so ON so.id = ba.order_id
                    WHERE so.state IN ('sale', 'done')
                    UNION ALL
                    SELECT sol.batch_id AS b_id, sol.product_uom_qty AS s_qty
                    FROM sale_order_line sol
                    JOIN sale_order so ON so.id = sol.order_id
                    WHERE so.state IN ('sale', 'done') AND sol.batch_id IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM l4e_sale_order_batch_allocation ba WHERE ba.order_line_id = sol.id
                      )
                ) sub_sales
                GROUP BY b_id
            ) sales ON sales.batch_id = pb.id
            WHERE (pb.total_net_output_qty - COALESCE(sales.total_sold, 0.0)) > 0
        """)
        ids = [row[0] for row in self.env.cr.fetchall()]
        return [("id", "in", ids)]

    @api.model
    def _extract_filter_product_id(self, domain):
        prod_id = self.env.context.get("filter_product_id")
        if prod_id and isinstance(prod_id, int):
            return prod_id
        if domain:
            try:
                from odoo.fields import Domain
                dom_obj = Domain(domain)
                for leaf in dom_obj.iter_conditions():
                    if leaf.operator == "=" and leaf.field_expr in ("product_id", "output_line_ids.product_id"):
                        if isinstance(leaf.value, int):
                            return leaf.value
            except Exception:
                pass
            if isinstance(domain, list):
                for item in domain:
                    if isinstance(item, (list, tuple)) and len(item) == 3:
                        if item[1] == "=" and item[0] in ("product_id", "output_line_ids.product_id") and isinstance(item[2], int):
                            return item[2]
        return None

    @api.model
    def _get_in_stock_batch_ids_by_product(self, product_id=None):
        if product_id:
            self.env.cr.execute("""
                SELECT pb.id
                FROM l4e_icecream_processing_batch pb
                LEFT JOIN (
                    SELECT batch_id, SUM(COALESCE(net_quantity, quantity)) AS prod_qty
                    FROM l4e_icecream_output_line
                    WHERE product_id = %s
                    GROUP BY batch_id
                ) prod ON prod.batch_id = pb.id
                LEFT JOIN (
                    SELECT b_id AS batch_id, SUM(s_qty) AS sold_qty
                    FROM (
                        SELECT ba.batch_id AS b_id, ba.quantity AS s_qty
                        FROM l4e_sale_order_batch_allocation ba
                        JOIN sale_order so ON so.id = ba.order_id
                        WHERE so.state IN ('sale', 'done') AND ba.product_id = %s
                        UNION ALL
                        SELECT sol.batch_id AS b_id, sol.product_uom_qty AS s_qty
                        FROM sale_order_line sol
                        JOIN sale_order so ON so.id = sol.order_id
                        WHERE so.state IN ('sale', 'done') AND sol.batch_id IS NOT NULL AND sol.product_id = %s
                          AND NOT EXISTS (
                              SELECT 1 FROM l4e_sale_order_batch_allocation ba WHERE ba.order_line_id = sol.id
                          )
                    ) sub_sales
                    GROUP BY b_id
                ) sales ON sales.batch_id = pb.id
                WHERE pb.state != 'cancel'
                  AND (
                      (prod.prod_qty IS NOT NULL AND (prod.prod_qty - COALESCE(sales.sold_qty, 0.0)) > 0)
                      OR
                      (prod.prod_qty IS NULL AND pb.product_id = %s AND (pb.total_net_output_qty - COALESCE(sales.sold_qty, 0.0)) > 0)
                  )
            """, (product_id, product_id, product_id, product_id))
        else:
            self.env.cr.execute("""
                SELECT pb.id
                FROM l4e_icecream_processing_batch pb
                LEFT JOIN (
                    SELECT b_id AS batch_id, SUM(s_qty) AS total_sold
                    FROM (
                        SELECT ba.batch_id AS b_id, ba.quantity AS s_qty
                        FROM l4e_sale_order_batch_allocation ba
                        JOIN sale_order so ON so.id = ba.order_id
                        WHERE so.state IN ('sale', 'done')
                        UNION ALL
                        SELECT sol.batch_id AS b_id, sol.product_uom_qty AS s_qty
                        FROM sale_order_line sol
                        JOIN sale_order so ON so.id = sol.order_id
                        WHERE so.state IN ('sale', 'done') AND sol.batch_id IS NOT NULL
                          AND NOT EXISTS (
                              SELECT 1 FROM l4e_sale_order_batch_allocation ba WHERE ba.order_line_id = sol.id
                          )
                    ) sub_sales
                    GROUP BY b_id
                ) sales ON sales.batch_id = pb.id
                WHERE pb.state != 'cancel'
                  AND (pb.total_net_output_qty - COALESCE(sales.total_sold, 0.0)) > 0
            """)
        return [row[0] for row in self.env.cr.fetchall()]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        if self.env.context.get("hide_depleted_batches"):
            prod_id = self._extract_filter_product_id(domain)
            in_stock_ids = self._get_in_stock_batch_ids_by_product(prod_id)
            extra = [("id", "in", in_stock_ids)]
            try:
                from odoo.fields import Domain
                domain = Domain(extra) & Domain(domain or [])
            except Exception:
                domain = extra + list(domain or [])
        return super().name_search(name=name, domain=domain, operator=operator, limit=limit)

    @api.model
    def web_search_read(self, domain=None, specification=None, offset=0, limit=None, order=None, count_limit=None):
        if self.env.context.get("hide_depleted_batches"):
            prod_id = self._extract_filter_product_id(domain)
            in_stock_ids = self._get_in_stock_batch_ids_by_product(prod_id)
            extra = [("id", "in", in_stock_ids)]
            try:
                from odoo.fields import Domain
                domain = Domain(extra) & Domain(domain or [])
            except Exception:
                domain = extra + list(domain or [])
        return super().web_search_read(
            domain=domain,
            specification=specification,
            offset=offset,
            limit=limit,
            order=order,
            count_limit=count_limit,
        )

    @api.depends("batch_number", "name")
    def _compute_display_name(self):
        for batch in self:
            batch.display_name = batch.batch_number or batch.name or ""

    # ─── Daily Auto-Sequencing: BATCH-DD-MMM-YY-001 (Resets Daily) ────────────

    @api.model
    def _get_default_batch_number(self, proc_date=None):
        if not proc_date:
            proc_date = fields.Date.context_today(self)
        if isinstance(proc_date, str):
            proc_date = fields.Date.from_string(proc_date)
        
        # Scoped strictly to the specific day (resets to 001 every day)
        existing_count = self.search_count([
            ("date", "=", proc_date),
        ])
        seq_num = existing_count + 1
        day_2digit = proc_date.strftime("%d")
        month_3letter = proc_date.strftime("%b").upper()
        year_2digit = proc_date.strftime("%y")
        return f"BATCH-{day_2digit}-{month_3letter}-{year_2digit}-{seq_num:03d}"

    @api.onchange("date")
    def _onchange_date(self):
        if self.state == "draft" and self.date:
            existing_count = self.env["l4e.icecream.processing.batch"].search_count([
                ("date", "=", self.date),
                ("id", "!=", self._origin.id if self._origin else False),
            ])
            day_2digit = self.date.strftime("%d")
            month_3letter = self.date.strftime("%b").upper()
            year_2digit = self.date.strftime("%y")
            self.batch_number = f"BATCH-{day_2digit}-{month_3letter}-{year_2digit}-{existing_count + 1:03d}"

    # ─── Multi-Ingredient Raw Material Lines ──────────────────────────────────

    raw_line_ids = fields.One2many(
        "l4e.icecream.raw.line",
        "batch_id",
        string="Raw Materials",
    )

    total_raw_qty = fields.Float(
        string="Total Raw Qty",
        compute="_compute_totals_and_yield",
        store=True,
        digits="Product Unit of Measure",
    )

    # ─── Finished Goods Output Lines ──────────────────────────────────────────

    output_line_ids = fields.One2many(
        "l4e.icecream.output.line",
        "batch_id",
        string="Finished Product",
    )

    @api.onchange("output_line_ids")
    def _onchange_output_line_ids(self):
        """When finished products or quantities change, if a product has a BOM,
        automatically update raw materials in the Raw Materials tab."""
        if self.state not in ("draft", "at_store"):
            return

        raw_components = {}
        has_any_bom = False

        for out_line in self.output_line_ids:
            if not out_line.product_id:
                continue
            fg_qty = out_line.net_quantity or out_line.quantity or 0.0
            if fg_qty <= 0:
                continue

            bom = self.env["mrp.bom"].search(
                [
                    "|",
                    ("product_id", "=", out_line.product_id.id),
                    "&",
                    ("product_id", "=", False),
                    ("product_tmpl_id", "=", out_line.product_id.product_tmpl_id.id),
                    ("company_id", "in", (self.company_id.id, False)),
                ],
                order="sequence, product_id, id",
                limit=1,
            )
            if bom and bom.bom_line_ids:
                has_any_bom = True
                factor = fg_qty / (bom.product_qty or 1.0)
                for bom_line in bom.bom_line_ids:
                    comp_id = bom_line.product_id.id
                    raw_components[comp_id] = raw_components.get(comp_id, 0.0) + (bom_line.product_qty * factor)

        if has_any_bom and raw_components:
            lines_cmds = []
            for comp_id, qty in raw_components.items():
                lines_cmds.append((0, 0, {
                    "product_id": comp_id,
                    "quantity": qty,
                }))
            self.raw_line_ids = [(5, 0, 0)] + lines_cmds

    def _populate_raw_materials_from_bom(self):
        for rec in self:
            if rec.state not in ("draft", "at_store"):
                continue
            raw_components = {}
            has_any_bom = False
            for out_line in rec.output_line_ids:
                if not out_line.product_id:
                    continue
                fg_qty = out_line.net_quantity or out_line.quantity or 0.0
                if fg_qty <= 0:
                    continue
                bom = self.env["mrp.bom"].search(
                    [
                        "|",
                        ("product_id", "=", out_line.product_id.id),
                        "&",
                        ("product_id", "=", False),
                        ("product_tmpl_id", "=", out_line.product_id.product_tmpl_id.id),
                        ("company_id", "in", (rec.company_id.id, False)),
                    ],
                    order="sequence, product_id, id",
                    limit=1,
                )
                if bom and bom.bom_line_ids:
                    has_any_bom = True
                    factor = fg_qty / (bom.product_qty or 1.0)
                    for bom_line in bom.bom_line_ids:
                        comp_id = bom_line.product_id.id
                        raw_components[comp_id] = raw_components.get(comp_id, 0.0) + (bom_line.product_qty * factor)

            if has_any_bom and raw_components:
                rec.raw_line_ids.unlink()
                raw_vals = [
                    {"batch_id": rec.id, "product_id": comp_id, "quantity": qty}
                    for comp_id, qty in raw_components.items()
                ]
                self.env["l4e.icecream.raw.line"].create(raw_vals)

    total_output_qty = fields.Float(
        string="Total Output",
        compute="_compute_totals_and_yield",
        store=True,
        digits="Product Unit of Measure",
    )

    yield_percentage = fields.Float(
        string="Yield %",
        compute="_compute_totals_and_yield",
        store=True,
        digits=(16, 2),
    )

    # ─── Wastage Lines ─────────────────────────────────────────────────────────

    wastage_line_ids = fields.One2many(
        "l4e.icecream.wastage.line",
        "batch_id",
        string="Wastage",
    )

    total_wastage_qty = fields.Float(
        string="Total Wastage",
        compute="_compute_totals_and_yield",
        store=True,
        digits="Product Unit of Measure",
    )

    total_net_output_qty = fields.Float(
        string="Total Net Output",
        compute="_compute_totals_and_yield",
        store=True,
        digits="Product Unit of Measure",
    )

    # ─── Locations ─────────────────────────────────────────────────────────────

    @api.model
    def _default_location(self, name):
        location = self.env["stock.location"].search(
            [
                ("name", "ilike", name),
                ("usage", "=", "internal"),
                ("active", "=", True),
            ],
            limit=1,
        )
        return location.id or False

    source_location_id = fields.Many2one(
        "stock.location",
        string="Source Location (Store)",
        required=True,
        tracking=True,
        default=lambda self: self._default_location("Store") or self._default_location("Stock"),
        domain="[('usage', '=', 'internal')]",
    )

    wip_location_id = fields.Many2one(
        "stock.location",
        string="Production Location",
        required=True,
        tracking=True,
        default=lambda self: self._default_location("Production"),
        domain="[('usage', '=', 'internal')]",
    )

    finished_location_id = fields.Many2one(
        "stock.location",
        string="Finished Goods Location",
        required=True,
        tracking=True,
        default=lambda self: self._default_location("Finished Goods"),
        domain="[('usage', '=', 'internal')]",
    )

    # ─── Cost Valuation Report Fields ─────────────────────────────────────────

    raw_cost_issued = fields.Float(
        string="Raw Cost Issued",
        compute="_compute_processing_cost_valuation",
        store=True,
        digits=(16, 2),
        help="Total standard cost of all raw ingredients issued into processing.",
    )

    finished_goods_value = fields.Float(
        string="Finished Goods Value",
        compute="_compute_processing_cost_valuation",
        store=True,
        digits=(16, 2),
        help="Total sales / valuation value of finished ice cream produced.",
    )

    value_difference = fields.Float(
        string="Value Variance / Gain",
        compute="_compute_processing_cost_valuation",
        store=True,
        digits=(16, 2),
        help="Difference between finished goods value and total ingredient cost issued.",
    )

    # ─── Linked Stock Pickings ────────────────────────────────────────────────

    raw_transfer_id = fields.Many2one(
        "stock.picking",
        string="Raw Material Transfer",
        readonly=True,
        copy=False,
        tracking=True,
    )

    raw_transfer_state = fields.Selection(
        related="raw_transfer_id.state",
        string="Raw Transfer State",
    )

    finished_transfer_id = fields.Many2one(
        "stock.picking",
        string="Finished Goods Transfer",
        readonly=True,
        copy=False,
        tracking=True,
    )

    finished_transfer_state = fields.Selection(
        related="finished_transfer_id.state",
        string="Finished Transfer State",
    )

    production_ids = fields.Many2many(
        "mrp.production",
        "l4e_processing_batch_mrp_production_rel",
        "batch_id",
        "production_id",
        string="Manufacturing Orders",
        copy=False,
    )

    production_count = fields.Integer(
        string="MO Count",
        compute="_compute_production_count",
    )

    @api.depends("production_ids")
    def _compute_production_count(self):
        for rec in self:
            rec.production_count = len(rec.production_ids)

    def action_view_manufacturing_orders(self):
        self.ensure_one()
        action = {
            "name": _("Manufacturing Orders"),
            "type": "ir.actions.act_window",
            "res_model": "mrp.production",
            "context": self.env.context,
        }
        if len(self.production_ids) == 1:
            action.update({
                "view_mode": "form",
                "res_id": self.production_ids[0].id,
            })
        else:
            action.update({
                "view_mode": "list,form",
                "domain": [("id", "in", self.production_ids.ids)],
            })
        return action

    remarks = fields.Text(string="Remarks")

    # ─── Audit / User Timestamps ──────────────────────────────────────────────

    processing_started_by = fields.Many2one("res.users", string="Started By", readonly=True, copy=False)
    processing_started_on = fields.Datetime(string="Started On", readonly=True, copy=False)
    processing_completed_by = fields.Many2one("res.users", string="Completed By", readonly=True, copy=False)
    processing_completed_on = fields.Datetime(string="Completed On", readonly=True, copy=False)

    # ─── Compute Methods ──────────────────────────────────────────────────────

    @api.depends("raw_line_ids.quantity", "output_line_ids.quantity", "wastage_line_ids.quantity")
    def _compute_totals_and_yield(self):
        for rec in self:
            total_raw = sum(rec.raw_line_ids.mapped("quantity"))
            total_out = sum(rec.output_line_ids.mapped("quantity"))
            total_waste = sum(rec.wastage_line_ids.mapped("quantity"))
            net_out = max(0.0, total_out - total_waste)
            rec.total_raw_qty = total_raw
            rec.total_output_qty = total_out
            rec.total_wastage_qty = total_waste
            rec.total_net_output_qty = net_out
            if total_raw > 0:
                rec.yield_percentage = (net_out / total_raw) * 100.0
            else:
                rec.yield_percentage = 0.0

    @api.depends("raw_line_ids.total_cost", "output_line_ids.total_value")
    def _compute_processing_cost_valuation(self):
        for rec in self:
            raw_cost = sum(rec.raw_line_ids.mapped("total_cost"))
            fg_value = sum(rec.output_line_ids.mapped("total_value"))
            rec.raw_cost_issued = raw_cost
            rec.finished_goods_value = fg_value
            rec.value_difference = fg_value - raw_cost

    # ─── ORM Create ───────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") in ("New", "/"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("l4e.icecream.processing.batch")
                    or "New"
                )
            if not vals.get("batch_number"):
                proc_date = vals.get("date") or fields.Date.context_today(self)
                vals["batch_number"] = self._get_default_batch_number(proc_date)
        return super().create(vals_list)

    # ─── Stock Picking Helpers ────────────────────────────────────────────────

    def _check_stock_availability(self):
        for line in self.raw_line_ids:
            if line.quantity <= 0:
                raise ValidationError(_("Quantity for raw material %s must be greater than zero.") % line.product_id.display_name)
            
            quants = self.env["stock.quant"].search([
                ("product_id", "=", line.product_id.id),
                ("location_id", "child_of", self.source_location_id.id),
            ])
            physical_qty = sum(quants.mapped("quantity"))
            if physical_qty < line.quantity:
                raise ValidationError(
                    _("Insufficient stock for %(product)s at %(location)s.\n"
                      "Physical Stock in Store: %(available).2f %(uom)s\n"
                      "Required for Batch: %(required).2f %(uom)s\n\n"
                      "Please purchase / receive or transfer stock into %(location)s first.")
                    % {
                        "product": line.product_id.display_name,
                        "location": self.source_location_id.display_name,
                        "available": physical_qty,
                        "required": line.quantity,
                        "uom": line.uom_id.name if line.uom_id else "",
                    }
                )

    def _get_internal_picking_type(self):
        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "internal"),
                ("warehouse_id.company_id", "=", self.company_id.id),
            ],
            limit=1,
        )
        if not picking_type:
            picking_type = self.env["stock.picking.type"].search(
                [
                    ("code", "=", "internal"),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
        if not picking_type:
            raise ValidationError(
                _("No Internal Transfer Operation Type found for company %s.")
                % self.company_id.display_name
            )
        return picking_type

    def _get_production_or_adjustment_location(self):
        # 1. Standard virtual production location from XML ID
        loc = self.env.ref("stock.stock_location_production", raise_if_not_found=False)
        if not loc:
            loc = self.env.ref("stock.location_production", raise_if_not_found=False)

        # 2. Fallback to product property
        if not loc and self.output_line_ids and self.output_line_ids[0].product_id:
            loc = self.output_line_ids[0].product_id.property_stock_production

        # 3. Fallback: Search for any production location NOT inside warehouse
        wh_view_ids = self.env["stock.warehouse"].search([]).mapped("view_location_id").ids
        wh_loc_ids = self.env["stock.location"].search([("id", "child_of", wh_view_ids)]).ids if wh_view_ids else []

        if not loc or (loc and loc.id in wh_loc_ids):
            loc = self.env["stock.location"].search(
                [
                    ("usage", "=", "production"),
                    ("id", "not in", wh_loc_ids),
                ],
                limit=1,
            )

        # 4. Fallback to inventory adjustment virtual location
        if not loc:
            loc = self.env["stock.location"].search(
                [
                    ("usage", "=", "inventory"),
                    ("id", "not in", wh_loc_ids),
                ],
                limit=1,
            ) or self.env["stock.location"].search([("usage", "=", "inventory")], limit=1)
        return loc

    def _get_scrap_location(self):
        loc = self.env.ref("stock.stock_location_scrapped", raise_if_not_found=False)
        if not loc:
            loc = self.env.ref("stock.location_scrapped", raise_if_not_found=False)
        if not loc:
            loc = self.env["stock.location"].search(
                [("usage", "=", "inventory"), ("company_id", "in", [self.company_id.id, False])],
                order="company_id desc, id asc",
                limit=1,
            )
        if not loc:
            loc = self.env["stock.location"].search([("usage", "=", "inventory")], limit=1)
        return loc

    # ─── Button Actions ────────────────────────────────────────────────────────

    def action_submit_request(self):
        """Submit the FG request to At Store stage and notify Store users."""
        self.ensure_one()
        if self.state != "draft":
            raise ValidationError(_("Only Draft batches can be submitted."))
        if not self.output_line_ids:
            raise ValidationError(_("Please add at least one Finished Product before submitting the request."))

        # Populate raw materials from BOM if not already populated
        if not self.raw_line_ids:
            self._populate_raw_materials_from_bom()

        self.write({"state": "at_store"})
        self._notify_store_users_fg_request()
        return True

    def _notify_store_users_fg_request(self):
        self.ensure_one()
        try:
            # Find all active Store and Production users
            notify_users = self.env["res.users"].sudo().search([
                ("active", "=", True),
                "|",
                ("is_store_user", "=", True),
                ("is_production_user", "=", True),
            ])
            # Fallback for store users if none flagged
            if not notify_users.filtered(lambda u: getattr(u, "is_store_user", False)):
                stock_group = self.env.ref("stock.group_stock_user", raise_if_not_found=False)
                if stock_group:
                    notify_users |= stock_group.users.filtered(lambda u: u.active)
            # Fallback for production users if none flagged
            if not notify_users.filtered(lambda u: getattr(u, "is_production_user", False)):
                mrp_group = self.env.ref("mrp.group_mrp_user", raise_if_not_found=False)
                if mrp_group:
                    notify_users |= mrp_group.users.filtered(lambda u: u.active)

            recipients = notify_users.filtered(lambda u: u.id != self.env.user.id and u.partner_id)
            if not recipients:
                return

            item_rows = []
            for line in self.output_line_ids:
                qty = line.net_quantity or line.quantity or 0.0
                uom_name = line.uom_id.name if line.uom_id else ""
                item_rows.append(f"<li><b>{line.product_id.display_name}</b>: {qty} {uom_name}</li>")
            items_html = f"<ul>{''.join(item_rows)}</ul>" if item_rows else ""

            body = Markup(
                f"<p><b>FG Request Submitted (At Store)</b></p>"
                f"<ul>"
                f"<li><b>Batch Number:</b> {self.batch_number or self.name}</li>"
                f"<li><b>Requested Date:</b> {self.date or ''}</li>"
                f"<li><b>Requested By:</b> {self.env.user.name}</li>"
                f"</ul>"
                f"<p><b>Requested Finished Products:</b></p>"
                f"{items_html}"
            )
            subject = f"FG Request Submitted: {self.batch_number or self.name}"

            partner_ids = recipients.mapped("partner_id").ids
            message = self.message_post(
                body=body,
                subject=subject,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                partner_ids=partner_ids,
            )

            for user in recipients:
                notif = self.env["mail.notification"].sudo().search(
                    [
                        ("mail_message_id", "=", message.id),
                        ("res_partner_id", "=", user.partner_id.id),
                    ],
                    limit=1,
                )
                if notif:
                    notif.sudo().write({"notification_type": "inbox", "is_read": False})
                else:
                    self.env["mail.notification"].sudo().create(
                        {
                            "mail_message_id": message.id,
                            "res_partner_id": user.partner_id.id,
                            "notification_type": "inbox",
                            "notification_status": "sent",
                            "is_read": False,
                        }
                    )

            # Schedule Activity for Store and Production Users
            todo_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
            todo_type_id = todo_type.id if todo_type else False
            if todo_type_id:
                for user in recipients:
                    existing_act = self.env["mail.activity"].sudo().search([
                        ("res_model", "=", self._name),
                        ("res_id", "=", self.id),
                        ("user_id", "=", user.id),
                        ("activity_type_id", "=", todo_type_id),
                    ], limit=1)
                    if not existing_act:
                        self.sudo().activity_schedule(
                            activity_type_id=todo_type_id,
                            user_id=user.id,
                            summary=_("FG Request: %s") % (self.batch_number or self.name),
                            note=body,
                        )

            # Direct Message in Discuss chat with each user
            author_id = self.env.user.partner_id.id if self.env.user.partner_id else False
            for user in recipients:
                if user.partner_id and user.partner_id.id != author_id:
                    try:
                        chat = self.env["discuss.channel"].sudo()._get_or_create_chat(
                            partners_to=[user.partner_id.id], pin=True
                        )
                        if chat:
                            chat.sudo().message_post(
                                body=body,
                                message_type="comment",
                                subtype_xmlid="mail.mt_comment",
                                author_id=author_id,
                            )
                    except Exception as e:
                        _logger.warning("Could not send FG request chat message to user %s: %s", user.name, e)
        except Exception as e:
            _logger.exception("Error sending FG request notification to store/production users: %s", e)

    def action_store_confirm(self):
        """Confirm raw materials in At Store stage without moving the stage."""
        self.ensure_one()
        user = self.env.user
        is_admin = user._is_admin() or user.has_group("base.group_system")
        is_store = bool(getattr(user, "is_store_user", False) or user.has_group("stock.group_stock_user") or is_admin)
        if not is_store:
            raise UserError(_("Only Store users are authorized to confirm raw materials."))

        if self.state != "at_store":
            raise ValidationError(_("Only batches in 'At Store' stage can be confirmed."))
        if not self.raw_line_ids:
            raise ValidationError(_("Please add at least one raw material ingredient before confirming."))
        self.write({"is_store_confirmed": True})
        self.message_post(body=_("Raw materials confirmed by Store User. Ready for Transfer."))
        return True

    def action_transfer(self):
        """Execute stock transfer of raw materials to Production and advance to Processing."""
        self.ensure_one()
        user = self.env.user
        is_admin = user._is_admin() or user.has_group("base.group_system")
        is_store = bool(getattr(user, "is_store_user", False) or user.has_group("stock.group_stock_user") or is_admin)
        if not is_store:
            raise UserError(_("Only Store users are authorized to transfer raw materials to production."))

        if self.state != "at_store":
            raise ValidationError(_("Only batches in 'At Store' stage can be transferred."))
        if not self.is_store_confirmed:
            raise ValidationError(_("Please click 'Confirm' before transferring."))

        # Mark store activities as done
        try:
            todo_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
            if todo_type:
                acts = self.env["mail.activity"].sudo().search([
                    ("res_model", "=", self._name),
                    ("res_id", "=", self.id),
                    ("activity_type_id", "=", todo_type.id),
                ])
                if acts:
                    acts.action_feedback(feedback=_("Raw materials transferred to production."))
        except Exception as e:
            _logger.warning("Error marking store activities done: %s", e)

        return self.action_start_processing()

    def action_start_processing(self):
        """Move all raw material ingredients from Store -> Production location."""
        self.ensure_one()
        if self.state not in ("draft", "at_store"):
            raise ValidationError(_("Only Draft or At Store batches can be started."))
        if not self.raw_line_ids:
            raise ValidationError(_("Please add at least one raw material ingredient in the Raw Materials tab."))

        # Check stock availability in Store
        self._check_stock_availability()

        picking_type = self._get_internal_picking_type()
        raw_picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": self.source_location_id.id,
            "location_dest_id": self.wip_location_id.id,
            "origin": self.name,
            "company_id": self.company_id.id,
        })

        moves = self.env["stock.move"]
        for line in self.raw_line_ids:
            move = self.env["stock.move"].create({
                "description_picking": _("Issue: %s") % line.product_id.display_name,
                "product_id": line.product_id.id,
                "product_uom_qty": line.quantity,
                "product_uom": line.uom_id.id,
                "location_id": self.source_location_id.id,
                "location_dest_id": self.wip_location_id.id,
                "picking_id": raw_picking.id,
                "company_id": self.company_id.id,
            })
            moves |= move

        moves._action_confirm()
        for move in moves:
            move.quantity = move.product_uom_qty
            move.picked = True
        moves._action_done()

        self.write({
            "state": "processing",
            "raw_transfer_id": raw_picking.id,
            "processing_started_by": self.env.user.id,
            "processing_started_on": fields.Datetime.now(),
        })

    def action_complete_processing(self):
        """
        Complete processing:
        1. Consume all raw ingredients from Production -> Virtual/Production.
        2. Produce all finished ice cream goods from Virtual/Production -> Finished Goods Location.
        """
        self.ensure_one()
        if self.state != "processing":
            raise ValidationError(_("Only Processing batches can be completed."))
        if not self.output_line_ids:
            raise ValidationError(_("Please add at least one finished product output line in the Finished Product tab."))
        for line in self.output_line_ids:
            if line.quantity <= 0:
                raise ValidationError(_("Output quantity for %s must be greater than zero.") % line.product_id.display_name)

        # Wastage validations
        for w_line in self.wastage_line_ids:
            if w_line.quantity < 0:
                raise ValidationError(_("Wastage quantity cannot be negative."))

        for out_line in self.output_line_ids:
            total_produced = sum(o.quantity for o in self.output_line_ids if o.product_id == out_line.product_id)
            total_waste = sum(w.quantity for w in self.wastage_line_ids if w.product_id == out_line.product_id)
            if total_waste > total_produced:
                raise ValidationError(
                    _("Total wastage for %(product)s (%(waste)s) cannot exceed total quantity produced (%(produced)s).")
                    % {
                        "product": out_line.product_id.display_name,
                        "waste": total_waste,
                        "produced": total_produced,
                    }
                )

        prod_location = self._get_production_or_adjustment_location()
        created_mos = self.env["mrp.production"]

        for out_line in self.output_line_ids:
            net_qty = out_line.net_quantity if out_line.net_quantity is not False else out_line.quantity
            if net_qty <= 0:
                continue

            bom = self.env["mrp.bom"].search(
                [
                    "|",
                    ("product_id", "=", out_line.product_id.id),
                    "&",
                    ("product_id", "=", False),
                    ("product_tmpl_id", "=", out_line.product_id.product_tmpl_id.id),
                    ("company_id", "in", (self.company_id.id, False)),
                ],
                order="sequence, product_id, id",
                limit=1,
            )

            origin_ref = f"{self.name} ({self.batch_number})" if self.batch_number else self.name
            mo_vals = {
                "product_id": out_line.product_id.id,
                "product_qty": net_qty,
                "product_uom_id": out_line.uom_id.id,
                "company_id": self.company_id.id,
                "location_src_id": self.wip_location_id.id,
                "location_dest_id": self.finished_location_id.id,
                "origin": origin_ref,
            }
            if bom:
                mo_vals["bom_id"] = bom.id

            mo = self.env["mrp.production"].create(mo_vals)

            # Synchronize MO components with batch's raw materials (including any extra added by Store User)
            if self.raw_line_ids:
                existing_raw = {m.product_id.id: m for m in mo.move_raw_ids}
                batch_raw_product_ids = set(self.raw_line_ids.mapped("product_id.id"))
                for r_line in self.raw_line_ids:
                    if r_line.product_id.id in existing_raw:
                        existing_raw[r_line.product_id.id].write({
                            "product_uom_qty": r_line.quantity,
                            "product_uom": r_line.uom_id.id,
                            "location_id": self.wip_location_id.id,
                        })
                    else:
                        dest_loc = (
                            prod_location.id
                            if prod_location
                            else (
                                out_line.product_id.property_stock_production.id
                                or self.wip_location_id.id
                            )
                        )
                        self.env["stock.move"].create({
                            "description_picking": _("Consume: %s") % r_line.product_id.display_name,
                            "raw_material_production_id": mo.id,
                            "product_id": r_line.product_id.id,
                            "product_uom": r_line.uom_id.id,
                            "product_uom_qty": r_line.quantity,
                            "location_id": self.wip_location_id.id,
                            "location_dest_id": dest_loc,
                            "company_id": self.company_id.id,
                        })
                for prod_id, move in existing_raw.items():
                    if prod_id not in batch_raw_product_ids:
                        move.unlink()

            # Set producing lot / batch number
            if out_line.product_id.tracking != "none" and self.batch_number:
                lot = self.env["stock.lot"].search([
                    ("name", "=", self.batch_number),
                    ("product_id", "=", out_line.product_id.id),
                    ("company_id", "=", self.company_id.id),
                ], limit=1)
                if not lot:
                    lot = self.env["stock.lot"].create({
                        "name": self.batch_number,
                        "product_id": out_line.product_id.id,
                        "company_id": self.company_id.id,
                        "batch_id": self.id,
                    })
                elif not lot.batch_id:
                    lot.batch_id = self.id
                if hasattr(mo, "lot_producing_id"):
                    mo.lot_producing_id = lot.id

            mo.action_confirm()

            # Register wastage as scrap if present
            if self.wastage_line_ids:
                scrap_loc = self._get_scrap_location()
                for w_line in self.wastage_line_ids:
                    if w_line.quantity > 0 and w_line.product_id == out_line.product_id:
                        try:
                            self.env["stock.scrap"].create({
                                "product_id": w_line.product_id.id,
                                "scrap_qty": w_line.quantity,
                                "product_uom_id": w_line.uom_id.id,
                                "production_id": mo.id,
                                "location_id": self.wip_location_id.id,
                                "scrap_location_id": scrap_loc.id if scrap_loc else False,
                                "company_id": self.company_id.id,
                                "origin": origin_ref,
                            })
                        except Exception as e:
                            _logger.warning("Could not create stock.scrap for MO %s: %s", mo.name, e)

            created_mos |= mo

        self.write({
            "state": "completed",
            "production_ids": [(6, 0, created_mos.ids)],
            "processing_completed_by": self.env.user.id,
            "processing_completed_on": fields.Datetime.now(),
        })

        mo_names = ", ".join(created_mos.mapped("name"))
        self.message_post(
            body=_("Manufacturing Order(s) created: <b>%s</b>. Stock will move when MO is marked Done.") % mo_names
        )

        # Notify and schedule activity for Production User(s)
        self._notify_production_users_mo_created(created_mos)

    def _notify_production_users_mo_created(self, created_mos):
        self.ensure_one()
        if not created_mos:
            return
        try:
            prod_users = self.env["res.users"].sudo().search([
                ("active", "=", True),
                ("is_production_user", "=", True),
            ])
            if not prod_users:
                mrp_group = self.env.ref("mrp.group_mrp_user", raise_if_not_found=False)
                if mrp_group:
                    prod_users = mrp_group.users.filtered(lambda u: u.active and u.id != self.env.user.id)

            todo_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
            todo_type_id = todo_type.id if todo_type else False

            partner_ids = prod_users.mapped("partner_id").ids

            for mo in created_mos:
                mo_body = Markup(
                    f"<p><b>Manufacturing Order Created from Batch {self.batch_number or self.name}</b></p>"
                    f"<ul>"
                    f"<li><b>MO Reference:</b> {mo.name}</li>"
                    f"<li><b>Finished Product:</b> {mo.product_id.display_name}</li>"
                    f"<li><b>Quantity to Produce:</b> {mo.product_qty} {mo.product_uom_id.name if mo.product_uom_id else ''}</li>"
                    f"<li><b>Batch Number:</b> {self.batch_number or self.name}</li>"
                    f"<li><b>Processing Order:</b> {self.name}</li>"
                    f"</ul>"
                    f"<p>Please proceed with production and mark as Done.</p>"
                )
                mo_subject = f"Manufacturing Order Ready: {mo.name} ({self.batch_number or self.name})"

                # Post message on MO chatter
                msg = mo.message_post(
                    body=mo_body,
                    subject=mo_subject,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                    partner_ids=partner_ids,
                )

                for user in prod_users.filtered(lambda u: u.active and u.partner_id):
                    # Discuss inbox notification
                    notif = self.env["mail.notification"].sudo().search([
                        ("mail_message_id", "=", msg.id),
                        ("res_partner_id", "=", user.partner_id.id),
                    ], limit=1)
                    if notif:
                        notif.sudo().write({"notification_type": "inbox", "is_read": False})
                    else:
                        self.env["mail.notification"].sudo().create({
                            "mail_message_id": msg.id,
                            "res_partner_id": user.partner_id.id,
                            "notification_type": "inbox",
                            "notification_status": "sent",
                            "is_read": False,
                        })

                    # Schedule Activity (Systray clock) on the MO
                    if todo_type_id:
                        existing_act = self.env["mail.activity"].sudo().search([
                            ("res_model", "=", "mrp.production"),
                            ("res_id", "=", mo.id),
                            ("user_id", "=", user.id),
                            ("activity_type_id", "=", todo_type_id),
                        ], limit=1)
                        if not existing_act:
                            mo.sudo().activity_schedule(
                                activity_type_id=todo_type_id,
                                user_id=user.id,
                                summary=_("Produce MO: %s (%s)") % (mo.name, self.batch_number or self.name),
                                note=mo_body,
                            )
        except Exception as e:
            _logger.exception("Error sending MO notification/activity to production users: %s", e)

    def action_reset_draft(self):
        self.write({"state": "draft", "is_store_confirmed": False})

    def action_cancel(self):
        self.write({"state": "cancel"})

    def action_view_raw_transfer(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Raw Material Transfer"),
            "res_model": "stock.picking",
            "res_id": self.raw_transfer_id.id,
            "view_mode": "form",
        }

    def action_view_finished_transfer(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Finished Goods Transfer"),
            "res_model": "stock.picking",
            "res_id": self.finished_transfer_id.id,
            "view_mode": "form",
        }
