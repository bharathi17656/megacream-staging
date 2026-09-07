# -*- coding: utf-8 -*-

from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            order._notify_store_production_users()
        return res

    def _notify_store_production_users(self):
        self.ensure_one()
        if not self.env.user.is_sales_user:
            return

        notify_users = self.env["res.users"].search(
            [
                "|",
                ("is_store_user", "=", True),
                ("is_production_user", "=", True),
            ]
        )
        if not notify_users:
            return

        partner_ids = notify_users.mapped("partner_id").ids
        body = (
            "<p><b>Sales Order Confirmed</b></p>"
            "<ul>"
            "<li>Order: %s</li>"
            "<li>Customer: %s</li>"
            "<li>Salesperson: %s</li>"
            "<li>Order Date: %s</li>"
            "<li>Total: %s %s</li>"
            "</ul>"
        ) % (
            self.name,
            self.partner_id.name or "",
            self.env.user.name,
            self.date_order,
            self.amount_total,
            self.currency_id.name or "",
        )
        self.message_notify(
            body=body,
            partner_ids=partner_ids,
            subject="Sales Order Confirmed: %s" % self.name,
        )
