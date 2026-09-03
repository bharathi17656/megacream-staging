# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    @api.model_create_multi
    def create(self, vals_list):
        store_loc = self.env["stock.location"].search(
            [("name", "ilike", "Store"), ("usage", "=", "internal"), ("active", "=", True)],
            limit=1,
        )
        if store_loc:
            for vals in vals_list:
                picking_type_id = vals.get("picking_type_id")
                if picking_type_id:
                    picking_type = self.env["stock.picking.type"].browse(picking_type_id)
                    # For incoming Receipts: default destination to WH/Store
                    if picking_type.code == "incoming" and not vals.get("location_dest_id"):
                        vals["location_dest_id"] = store_loc.id

        return super().create(vals_list)


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    def _get_store_location(self):
        return self.env["stock.location"].search(
            [("name", "ilike", "Store"), ("usage", "=", "internal"), ("active", "=", True)],
            limit=1,
        )

    @api.model_create_multi
    def create(self, vals_list):
        warehouses = super().create(vals_list)
        store_loc = self._get_store_location()
        if store_loc:
            for w in warehouses:
                if w.in_type_id and not w.in_type_id.default_location_dest_id:
                    w.in_type_id.default_location_dest_id = store_loc.id
        return warehouses