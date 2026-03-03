# models/hr_employee.py
from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    esi_amount = fields.Float(string="ESI Amount")
    bank_amount = fields.Float(string="Bank Salary Amount")
    cash_amount = fields.Float(string="Cash Salary Amount")