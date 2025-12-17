# models/hr_attendance.py
from odoo import models, fields, api

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    eligibled = fields.Boolean(string='Eligible for Payroll', default=False)
    eligibility_note = fields.Char(string='Eligibility Note')
