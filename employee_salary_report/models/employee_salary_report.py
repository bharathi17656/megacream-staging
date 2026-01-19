class EmployeeSalaryReport(models.Model):
    _name = 'employee.salary.report'
    _description = 'Employee Salary Report'
    _order = 'date_from desc'

    employee_id = fields.Many2one('hr.employee', required=True)
    contract_id = fields.Many2one('hr.version')
    payslip_id = fields.Many2one('hr.payslip', ondelete='cascade')

    date_from = fields.Date()
    date_to = fields.Date()
    month_name = fields.Char(compute='_compute_month_name', store=True)

    # Days
    total_days_in_month = fields.Float(readonly=True)
    total_working_days_in_month = fields.Float(readonly=True)

    # ======================
    # EARNINGS (EXCEL BASED)
    # ======================
    basic_da = fields.Float(string="Basic + DA", compute='_compute_from_payslip', store=True)
    hra = fields.Float(string="HRA", compute='_compute_from_payslip', store=True)
    conveyance = fields.Float(string="Conveyance", compute='_compute_from_payslip', store=True)
    spl_allowance = fields.Float(string="Special Allowance", compute='_compute_from_payslip', store=True)
    bonus = fields.Float(string="Bonus", compute='_compute_from_payslip', store=True)
    leave_encashment = fields.Float(string="Leave Encashment", compute='_compute_from_payslip', store=True)

    gross_salary = fields.Float(string="Gross Salary", compute='_compute_from_payslip', store=True)

    # ======================
    # DEDUCTIONS
    # ======================
    employee_pf = fields.Float(string="Employee PF", compute='_compute_from_payslip', store=True)
    employee_esi = fields.Float(string="Employee ESI", compute='_compute_from_payslip', store=True)
    professional_tax = fields.Float(string="Professional Tax", compute='_compute_from_payslip', store=True)
    other_deduction = fields.Float(string="Other Deduction", compute='_compute_from_payslip', store=True)

    # ======================
    # EMPLOYER CONTRIBUTION
    # ======================
    employer_pf = fields.Float(string="Employer PF", compute='_compute_from_payslip', store=True)
    employer_esi = fields.Float(string="Employer ESI", compute='_compute_from_payslip', store=True)
    gratuity = fields.Float(string="Gratuity", compute='_compute_from_payslip', store=True)

    # ======================
    # FINAL
    # ======================
    net_salary = fields.Float(string="Net Salary", compute='_compute_from_payslip', store=True)
    monthly_ctc = fields.Float(string="Monthly CTC", compute='_compute_from_payslip', store=True)
    yearly_ctc = fields.Float(string="Yearly CTC", compute='_compute_from_payslip', store=True)



    @api.depends('payslip_id')
    def _compute_from_payslip(self):
        pass
        # for rec in self:
        #     # Reset all computed fields
        #     for field in RULE_MAP.values():
        #         rec[field] = 0.0
    
        #     rec.monthly_ctc = 0.0
        #     rec.yearly_ctc = 0.0
    
        #     slip = rec.payslip_id
        #     if not slip:
        #         continue
    
        #     # Days
        #     rec.total_days_in_month = slip.total_days_in_month or 0
        #     rec.total_working_days_in_month = slip.total_working_days_in_month or 0
    
        #     # Read payslip lines
        #     for line in slip.line_ids:
        #         code = line.code
        #         if code in RULE_MAP:
        #             field_name = RULE_MAP[code]
        #             rec[field_name] += line.total
    
        #     # Monthly CTC = Gross + Employer contributions
        #     rec.monthly_ctc = (
        #         rec.gross_salary
        #         + rec.employer_pf
        #         + rec.employer_esi
        #         + rec.gratuity
        #     )
    
        #     rec.yearly_ctc = rec.monthly_ctc * 12


    @api.depends('date_from')
    def _compute_month_name(self):
        for rec in self:
            pass
            # rec.month_name = (
            #     fields.Date.to_date(rec.date_from).strftime("%B %Y")
            #     if rec.date_from else False
            # )





