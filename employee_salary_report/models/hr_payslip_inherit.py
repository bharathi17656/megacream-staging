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

    # # ----------------------------------------------------
    # # Create Salary Report when Payslip is PAID
    # # ----------------------------------------------------
    # def action_payslip_paid(self):
    #     res = super().action_payslip_paid()

    #     SalaryReport = self.env['employee.salary.report']

    #     for slip in self:
    #         # 🔒 Prevent duplicate creation
    #         if SalaryReport.search([('payslip_id', '=', slip.id)], limit=1):
    #             continue

    #         SalaryReport.create({
    #             'employee_id': slip.employee_id.id,
    #             'contract_id': slip.version_id.id if slip.version_id else False,
    #             'payslip_id': slip.id,
    #             'date_from': slip.date_from,
    #             'date_to': slip.date_to,
    #         })

    #     return res

    def action_payslip_paid(self):
        res = super().action_payslip_paid()
    
        SalaryReport = self.env['employee.salary.report']
    
        for slip in self:
            # 🔁 Always remove existing report for this payslip
            old_reports = SalaryReport.search([('payslip_id', '=', slip.id)])
            if old_reports:
                old_reports.unlink()
    
            # ✅ Create fresh report
            SalaryReport.create({
                'employee_id': slip.employee_id.id,
                'contract_id': slip.version_id.id if slip.version_id else False,
                'payslip_id': slip.id,
                'date_from': slip.date_from,
                'date_to': slip.date_to,
            })
            
    def unlink(self):
        self.env['employee.salary.report'].search([
            ('payslip_id', 'in', self.ids)
        ]).unlink()

        return super().unlink()


