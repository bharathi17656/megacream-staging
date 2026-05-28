from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    total_allowances = fields.Monetary(
        string='Total Allowances',
        currency_field='currency_id',
        compute='_compute_total_allowances',
        store=True,
    )

    increment_ids = fields.One2many(
        comodel_name='hr.employee.increment',
        inverse_name='employee_id',
        string='Increments',
    )

    @api.depends('cash_amount', 'bank_amount')
    def _compute_total_allowances(self):
        for emp in self:
            emp.total_allowances = emp.cash_amount + emp.bank_amount

    @api.constrains('wage', 'cash_amount', 'bank_amount')
    def _check_allowances_not_exceed_wage(self):
        if self.env.context.get('skip_allowance_check'):
            return
        for emp in self:
            wage = emp.wage or 0.0
            total = emp.cash_amount + emp.bank_amount
            if wage and total > wage:
                raise ValidationError(_(
                    'The total of all allowances (%(total).2f) cannot exceed '
                    "the employee's wage (%(wage).2f).\n\n"
                    'Please reduce one or more allowance values.',
                    total=total,
                    wage=wage,
                ))