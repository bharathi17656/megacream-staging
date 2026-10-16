# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    batch_number = fields.Char(
        string="Batch Number",
        copy=False,
        tracking=True,
    )
    batch_id = fields.Many2one(
        "l4e.icecream.processing.batch",
        string="Processing Batch",
        copy=False,
        index=True,
    )

    def init(self):
        super().init()
        # Backfill batch_number on existing MOs linked to processing batches
        self.env.cr.execute("""
            UPDATE mrp_production mp
            SET batch_number = pb.batch_number,
                batch_id = pb.id
            FROM l4e_processing_batch_mrp_production_rel rel
            JOIN l4e_icecream_processing_batch pb ON pb.id = rel.batch_id
            WHERE mp.id = rel.production_id
              AND (mp.batch_number IS NULL OR mp.batch_number = '');
        """)

    @api.onchange("batch_number")
    def _onchange_batch_number(self):
        for production in self:
            if production.batch_number and production.product_id and production.product_id.tracking != "none":
                lot = self.env["stock.lot"].search([
                    ("name", "=", production.batch_number),
                    ("product_id", "=", production.product_id.id),
                    ("company_id", "=", production.company_id.id),
                ], limit=1)
                if not lot:
                    lot = self.env["stock.lot"].create({
                        "name": production.batch_number,
                        "product_id": production.product_id.id,
                        "company_id": production.company_id.id,
                        "batch_id": production.batch_id.id if production.batch_id else False,
                    })
                elif production.batch_id and not lot.batch_id:
                    lot.batch_id = production.batch_id.id
                if hasattr(production, "lot_producing_id"):
                    production.lot_producing_id = lot.id

    def write(self, vals):
        res = super().write(vals)
        if "batch_number" in vals:
            for production in self:
                if production.batch_number and production.product_id and production.product_id.tracking != "none":
                    lot = self.env["stock.lot"].search([
                        ("name", "=", production.batch_number),
                        ("product_id", "=", production.product_id.id),
                        ("company_id", "=", production.company_id.id),
                    ], limit=1)
                    if not lot:
                        lot = self.env["stock.lot"].create({
                            "name": production.batch_number,
                            "product_id": production.product_id.id,
                            "company_id": production.company_id.id,
                            "batch_id": production.batch_id.id if production.batch_id else False,
                        })
                    elif production.batch_id and not lot.batch_id:
                        lot.batch_id = production.batch_id.id
                    if hasattr(production, "lot_producing_id") and production.lot_producing_id != lot:
                        production.lot_producing_id = lot.id
        return res

    @api.depends_context("uid")
    @api.depends("state", "product_qty", "qty_producing")
    def _compute_show_produce(self):
        super()._compute_show_produce()
        is_admin = self.env.is_admin() or self.env.user.has_group("base.group_system")
        is_prod = getattr(self.env.user, "is_production_user", False)
        is_store = getattr(self.env.user, "is_store_user", False)

        # Store user cannot see Produce or Produce All buttons unless they are production user or admin
        if is_store and not (is_prod or is_admin):
            for production in self:
                production.show_produce_all = False
                production.show_produce = False

    def button_mark_done(self):
        is_admin = self.env.is_admin() or self.env.user.has_group("base.group_system")
        is_prod = getattr(self.env.user, "is_production_user", False)
        is_store = getattr(self.env.user, "is_store_user", False)

        # Prevent store users from executing production
        if is_store and not (is_prod or is_admin):
            raise UserError(
                _("Store users are not authorized to produce Manufacturing Orders. Only Production users can perform Produce All.")
            )
        return super().button_mark_done()
