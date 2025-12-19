from odoo import models, fields, api
from datetime import datetime

class EmployeeSalaryReport(models.Model):
    _name = 'employee.salary.report'
    _description = 'Employee Salary Report'
    _rec_name = 'employee_id'
    _order = 'date_from desc'

    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    contract_id = fields.Many2one('hr.version', string="Contract")
    payslip_id = fields.Many2one('hr.payslip', string="Payslip", ondelete='cascade')
    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")
    month_name = fields.Char(string="Month", compute="_compute_month_name", store=True)

    total_days_in_month = fields.Float(string="Total Days in Month", readonly=True)
    total_working_days_in_month = fields.Float(string="Total Working Days in Month", readonly=True)
    
    gross_salary = fields.Float(string="Gross Salary")
    basic_da = fields.Float(string="Basic + DA", compute="_compute_salary_components", store=True)
    hra = fields.Float(string="HRA", compute="_compute_salary_components", store=True)
    spl_allowance = fields.Float(string="Special Allowance", compute="_compute_salary_components", store=True)
    conveyance = fields.Float(string="Conveyance", default=1600)
    employee_pf = fields.Float(string="Employee PF", compute="_compute_salary_components", store=True)
    employer_pf = fields.Float(string="Employer PF", compute="_compute_salary_components", store=True)
    employer_esi = fields.Float(string="Employer ESI", compute="_compute_salary_components", store=True)
    prof_tax = fields.Float(string="Profession Tax", default=200)
    other_deduction = fields.Float(string="Other Deduction", default=0)
    gratuity = fields.Float(string="Gratuity", compute="_compute_salary_components", store=True)
    bonus = fields.Float(string="Bonus", compute="_compute_salary_components", store=True)
    insurance = fields.Float(string="Insurance", default=1000)
    encashment_leave = fields.Float(string="Encashment of Leave", default=0)
    net_salary = fields.Float(string="Net Salary", compute="_compute_salary_components", store=True)
    ctc = fields.Float(string="CTC", compute="_compute_salary_components", store=True)
    monthly_ctc = fields.Float(string="Monthly (CTC)", compute="_compute_salary_components", store=True)
    yearly_ctc = fields.Float(string="Yearly (CTC)", compute="_compute_salary_components", store=True)

    @api.depends('date_from')
    def _compute_month_name(self):
        for rec in self:
            if rec.date_from:
                # store as "Month Year", e.g. "July 2025"
                rec.month_name = fields.Date.to_date(rec.date_from).strftime("%B %Y")
            else:
                rec.month_name = False

    @api.depends('gross_salary', 'conveyance', 'other_deduction', 'insurance', 'encashment_leave', 'prof_tax')
    def _compute_salary_components(self):
        for rec in self:
            gross = rec.gross_salary or 0.0
            rec.basic_da = gross * 0.45
            rec.hra = gross * 0.23
            rec.spl_allowance = gross - (rec.basic_da + rec.hra + (rec.conveyance or 0.0))

            # PF & ESI (rules based on provided spreadsheet; adjust if needed)
            rec.employee_pf = rec.contract_id.employee_pf 
            rec.employer_pf = rec.contract_id.employer_pf
            rec.employer_esi = 0

            # Gratuity & Bonus
            rec.gratuity = (rec.basic_da / 30) * 1.25
            rec.bonus = 0

            # Net Salary = gross - (employee_pf + prof_tax + other_deduction)
            rec.net_salary = gross - ((rec.employee_pf or 0.0) + (rec.prof_tax or 0.0) + (rec.other_deduction or 0.0))

            # CTC calculation
            rec.ctc = gross + (rec.employer_pf or 0.0) + (rec.employer_esi or 0.0) + (rec.insurance or 0.0) + (rec.gratuity or 0.0) + (rec.bonus or 0.0) + (rec.encashment_leave or 0.0)
            rec.monthly_ctc = rec.ctc
            rec.yearly_ctc = (rec.ctc or 0.0) * 12
