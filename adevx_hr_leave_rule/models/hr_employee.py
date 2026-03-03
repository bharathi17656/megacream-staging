# models/hr_employee.py
from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    esi_amount = fields.Monetary(string="ESI Amount")
    bank_amount = fields.Monetary(string="Bank Salary Amount")
    cash_amount = fields.Monetary(string="Cash Salary Amount")
