# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = "mrp.production"

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
