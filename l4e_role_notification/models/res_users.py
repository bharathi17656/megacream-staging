# -*- coding: utf-8 -*-

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    is_store_user = fields.Boolean(
        string="Store User",
        default=False,
        help="Receives a notification in Odoo Discuss and order chatter when a Sales Order is created or confirmed by a Sales User.",
    )
    is_production_user = fields.Boolean(
        string="Production User",
        default=False,
        help="Receives a notification in Odoo Discuss and order chatter when a Sales Order is created or confirmed by a Sales User.",
    )
    is_sales_user = fields.Boolean(
        string="Sales User",
        default=False,
        help="When this user creates or confirms a Sale Order, Store User(s) and Production User(s) are notified with the order details.",
    )
    is_purchase_user = fields.Boolean(
        string="Purchase User",
        default=False,
        help="User authorized to finalize and confirm Purchase Orders after Store User RFQ approval.",
    )
