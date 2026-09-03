# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class L4eIceCreamProcessingBatch(models.Model):
    _name = "l4e.icecream.processing.batch"
    _description = "Ice Cream Processing Batch"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _rec_name = "name"

    # Processing Order Reference (e.g. MC2026-00001)
    name = fields.Char(
        string="Order Reference",
        required=True,
        copy=False,
        default="New",
        tracking=True,
    )

    date = fields.Date(
        string="Processing Date",
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

    product_id = fields.Many2one(
        "product.product",
        string="Finished Ice Cream",
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
        string="Raw Materials / Ingredients Consumed",
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
        string="Finished Ice Cream Output",
    )

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

    remarks = fields.Text(string="Remarks")

    # ─── Audit / User Timestamps ──────────────────────────────────────────────

    processing_started_by = fields.Many2one("res.users", string="Started By", readonly=True, copy=False)
    processing_started_on = fields.Datetime(string="Started On", readonly=True, copy=False)
    processing_completed_by = fields.Many2one("res.users", string="Completed By", readonly=True, copy=False)
    processing_completed_on = fields.Datetime(string="Completed On", readonly=True, copy=False)

    # ─── Compute Methods ──────────────────────────────────────────────────────

    @api.depends("raw_line_ids.quantity", "output_line_ids.quantity")
    def _compute_totals_and_yield(self):
        for rec in self:
            total_raw = sum(rec.raw_line_ids.mapped("quantity"))
            total_out = sum(rec.output_line_ids.mapped("quantity"))
            rec.total_raw_qty = total_raw
            rec.total_output_qty = total_out
            if total_raw > 0:
                rec.yield_percentage = (total_out / total_raw) * 100.0
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
        # Must always be the standard Virtual Production location OUTSIDE any warehouse
        loc = self.env.ref("stock.location_production", raise_if_not_found=False)
        if not loc:
            wh_view_ids = self.env["stock.warehouse"].search([]).mapped("view_location_id").ids
            loc = self.env["stock.location"].search(
                [
                    ("usage", "=", "production"),
                    ("id", "not child_of", wh_view_ids),
                ],
                limit=1,
            )
        if not loc:
            loc = self.env.ref("stock.location_inventory", raise_if_not_found=False)
        return loc

    # ─── Button Actions ────────────────────────────────────────────────────────

    def action_start_processing(self):
        """Move all raw material ingredients from Store -> Production location."""
        self.ensure_one()
        if self.state != "draft":
            raise ValidationError(_("Only Draft batches can be started."))
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
            raise ValidationError(_("Please add at least one finished ice cream output line in the Finished Output tab."))
        for line in self.output_line_ids:
            if line.quantity <= 0:
                raise ValidationError(_("Output quantity for %s must be greater than zero.") % line.product_id.display_name)

        prod_location = self._get_production_or_adjustment_location()
        if not prod_location:
            raise ValidationError(_("No Virtual Production or Inventory Adjustment location found."))

        picking_type = self._get_internal_picking_type()
        finished_picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": self.wip_location_id.id,
            "location_dest_id": self.finished_location_id.id,
            "origin": self.name,
            "company_id": self.company_id.id,
        })

        consume_moves = self.env["stock.move"]
        for r_line in self.raw_line_ids:
            cm = self.env["stock.move"].create({
                "description_picking": _("Consume: %s") % r_line.product_id.display_name,
                "product_id": r_line.product_id.id,
                "product_uom_qty": r_line.quantity,
                "product_uom": r_line.uom_id.id,
                "location_id": self.wip_location_id.id,
                "location_dest_id": prod_location.id,
                "picking_id": finished_picking.id,
                "company_id": self.company_id.id,
            })
            consume_moves |= cm

        produce_moves = self.env["stock.move"]
        for out_line in self.output_line_ids:
            pm = self.env["stock.move"].create({
                "description_picking": _("Produce: %s") % out_line.product_id.display_name,
                "product_id": out_line.product_id.id,
                "product_uom_qty": out_line.quantity,
                "product_uom": out_line.uom_id.id,
                "location_id": prod_location.id,
                "location_dest_id": self.finished_location_id.id,
                "picking_id": finished_picking.id,
                "company_id": self.company_id.id,
            })
            produce_moves |= pm

        all_moves = consume_moves | produce_moves
        all_moves._action_confirm()

        # Set quantity, picked, and lot
        for move in all_moves:
            move.quantity = move.product_uom_qty
            move.picked = True
            if move in produce_moves and move.product_id.tracking != "none" and self.batch_number:
                lot = self.env["stock.lot"].search([
                    ("name", "=", self.batch_number),
                    ("product_id", "=", move.product_id.id),
                    ("company_id", "=", self.company_id.id),
                ], limit=1)
                if not lot:
                    lot = self.env["stock.lot"].create({
                        "name": self.batch_number,
                        "product_id": move.product_id.id,
                        "company_id": self.company_id.id,
                    })
                if move.move_line_ids:
                    for ml in move.move_line_ids:
                        ml.lot_id = lot.id
                else:
                    self.env["stock.move.line"].create({
                        "move_id": move.id,
                        "picking_id": finished_picking.id,
                        "product_id": move.product_id.id,
                        "product_uom_id": move.product_uom.id,
                        "quantity": move.product_uom_qty,
                        "location_id": move.location_id.id,
                        "location_dest_id": move.location_dest_id.id,
                        "lot_id": lot.id,
                    })

        all_moves._action_done()

        self.write({
            "state": "completed",
            "finished_transfer_id": finished_picking.id,
            "processing_completed_by": self.env.user.id,
            "processing_completed_on": fields.Datetime.now(),
        })

    def action_reset_draft(self):
        self.write({"state": "draft"})

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