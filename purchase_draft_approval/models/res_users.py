# -*- coding: utf-8 -*-
from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    store_indent = fields.Boolean(
        string='Store Indent',
        default=False,
        help="If enabled, this user does not need to specify a vendor "
             "when creating a Purchase Order in Draft state."
    )
