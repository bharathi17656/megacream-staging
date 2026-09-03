# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    party_order_count = fields.Integer(
        string="Party Orders",
        compute="_compute_party_fridge_stats",
    )
    missing_fridge_count = fields.Integer(
        string="Missing Fridges",
        compute="_compute_party_fridge_stats",
    )

    def _compute_party_fridge_stats(self):
        for partner in self:
            orders = self.env["sale.order"].search([
                ("partner_id", "=", partner.id),
                ("is_party_order", "=", True),
            ])
            partner.party_order_count = len(orders)
            partner.missing_fridge_count = sum(orders.mapped("fridge_qty_missing"))

    def action_view_party_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("l4e_party_report.action_party_report")
        action["domain"] = [("partner_id", "=", self.id), ("is_party_order", "=", True)]
        action["context"] = {"default_partner_id": self.id, "default_is_party_order": True}
        return action
