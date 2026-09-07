# -*- coding: utf-8 -*-

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    is_store_user = fields.Boolean(
        string="Store User",
        default=False,
        help="Receives a notification when a Sales Order is confirmed by a Sales User.",
    )
    is_production_user = fields.Boolean(
        string="Production User",
        default=False,
        help="Receives a notification when a Sales Order is confirmed by a Sales User.",
    )
    is_sales_user = fields.Boolean(
        string="Sales User",
        default=False,
        help="When this user confirms a Sale Order, Store User(s) and Production "
             "User(s) are notified with the order details.",
    )
