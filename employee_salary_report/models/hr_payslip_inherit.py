from odoo import models, fields, api, _

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    pay_period = fields.Char(string="Pay Period", store=True)

    # ----------------------------------------------------
    # Payslip Name + Pay Period
    # ----------------------------------------------------
    @api.depends('employee_id.legal_name', 'employee_id.lang', 'struct_id', 'date_from', 'date_to')
    def _compute_name(self):
        super()._compute_name()  # ✅ IMPORTANT

        formated_date_cache = {}
        for slip in self.filtered(lambda p: p.employee_id and p.date_from and p.date_to):
            slip.pay_period = slip._get_period_name(formated_date_cache)
            slip.name = _('Payslip for the month of - %s') % slip.pay_period

    # ----------------------------------------------------
    # Create Salary Report when Payslip is PAID
    # ----------------------------------------------------
    def action_payslip_paid(self):
        res = super().action_payslip_paid()

        SalaryReport = self.env['employee.salary.report']

        for slip in self:
            # 🔒 Prevent duplicate creation
            if SalaryReport.search([('payslip_id', '=', slip.id)], limit=1):
                continue

            SalaryReport.create({
                'employee_id': slip.employee_id.id,
                'contract_id': slip.version_id.id if slip.version_id else False,
                'payslip_id': slip.id,
                'date_from': slip.date_from,
                'date_to': slip.date_to,
            })

        return res

    # ----------------------------------------------------
    # Cleanup Salary Report on Payslip Delete
    # ----------------------------------------------------
    def unlink(self):
        self.env['employee.salary.report'].search([
            ('payslip_id', 'in', self.ids)
        ]).unlink()

        return super().unlink()


# class HrVersion(models.Model):
#     _inherit = 'hr.version'

#     # --- Component Fields ---
#     basic_da = fields.Float(string="Basic + DA", tracking=True)
#     hra = fields.Float(string="HRA", tracking=True)
#     spl_allowance = fields.Float(string="Special Allowance", tracking=True)
#     conveyance = fields.Float(string="Conveyance", tracking=True)

#     # --- Employee & Employer Contribution Fields ---
#     employee_pf = fields.Float(string="Employee PF Contribution", tracking=True)
#     employer_pf = fields.Float(string="Employer PF Contribution", tracking=True)
#     employer_prof_tax = fields.Float(string="Employer Contribution - Profession Tax", tracking=True)
#     insurance = fields.Float(string="Insurance", tracking=True)
#     gratuity = fields.Float(string="Gratuity", tracking=True)

#     # --- Computed Summary Fields ---
#     gross_salary_computed = fields.Float(string="Gross Salary (Computed)", compute="_compute_gross_salary", store=True)
#     net_salary = fields.Float(string="Net Salary", compute="_compute_salary_totals", store=True)
#     ctc = fields.Float(string="CTC", compute="_compute_salary_totals", store=True)
#     monthly_ctc = fields.Float(string="Monthly CTC", compute="_compute_salary_totals", store=True)
#     yearly_ctc = fields.Float(string="Yearly CTC", compute="_compute_salary_totals", store=True)

#     @api.depends('basic_da', 'hra', 'spl_allowance', 'conveyance')
#     def _compute_gross_salary(self):
#         for rec in self:
#             rec.gross_salary_computed = (
#                 rec.basic_da + rec.hra + rec.spl_allowance + rec.conveyance
#             )

#     @api.depends('gross_salary_computed', 'employee_pf', 'employer_pf', 'employer_prof_tax', 'gratuity', 'insurance')
#     def _compute_salary_totals(self):
#         for rec in self:
#             gross = rec.gross_salary_computed
#             if not gross:
#                 rec.net_salary = rec.ctc = rec.monthly_ctc = rec.yearly_ctc = 0.0
#                 continue

#             # Formulae
#             rec.ctc = gross + rec.employer_pf 
#             rec.net_salary = gross - (rec.employee_pf + rec.employer_prof_tax)
#             rec.monthly_ctc = rec.ctc + rec.gratuity + rec.insurance
#             rec.yearly_ctc = rec.monthly_ctc * 12

#     @api.model
#     def _get_whitelist_fields_from_template(self):
#         """Extend the whitelist to include custom salary fields."""
#         res = super()._get_whitelist_fields_from_template()
#         # Add our custom salary fields to the whitelist
#         res.extend([
#             'basic_da', 'hra', 'spl_allowance', 'conveyance',
#             'employee_pf', 'employer_pf', 'employer_prof_tax',
#             'insurance', 'gratuity'
#         ])
#         return res

#     @api.onchange('wage')
#     def _onchange_wage_update_components(self):
#         """Auto compute salary breakdown and contributions when wage changes."""
#         for rec in self:
#             if rec.wage:
#                 gross = rec.wage

#                 # Breakdown components (based on your ratios)
#                 rec.basic_da = gross * 0.45    # 45%
#                 rec.hra = gross * 0.23         # 23%
#                 rec.spl_allowance = gross * 0.256 # 25.6%
#                 rec.conveyance = gross * 0.064     # 6.4%

#                 # Contributions
#                 rec.employee_pf = 1800
#                 rec.employer_pf = 1950
#                 rec.employer_prof_tax = 200
#                 rec.insurance = 1000

#                 # Gratuity = Basic+DA / 30 * 1.25
#                 rec.gratuity = (rec.basic_da / 30) * 1.25
