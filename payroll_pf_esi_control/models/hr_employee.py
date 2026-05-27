# -*- coding: utf-8 -*-
from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    pf_eligible = fields.Boolean(string="PF", default=True)
    esi_eligible = fields.Boolean(string="ESI", default=True)
