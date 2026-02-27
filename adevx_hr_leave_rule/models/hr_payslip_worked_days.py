# models/hr_payslip_worked_days.py
from odoo import models, fields, api


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    # Override amount: remove compute so our explicit values stick.
    # Odoo's default makes amount a computed field (days × per_day from contract),
    # which overrides any value we set in compute_sheet.
    amount = fields.Monetary(
        string='Amount',
        compute=False,
        store=True,
        readonly=False,
    )
