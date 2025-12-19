from odoo import models, fields

class HREmployee(models.Model):
    _inherit = 'hr.employee'

    pf_account_number = fields.Char(string="PF A/C Number")
    uan_number = fields.Char(string="UAN")
