# models/hr_payslip.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta, datetime, time
import logging

_logger = logging.getLogger(__name__)

FESTIVAL_HOLIDAY_MODEL = 'hr.festival.holiday'


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # inside HrPayslip model 

    bank_payable = fields.Monetary(string="Bank Payable", readonly=True)
    cash_payable = fields.Monetary(string="Cash Payable", readonly=True)
    cash_print = fields.Boolean(string="Cash Print", default=True)
    bank_print = fields.Boolean(string="Bank Print", default=True)

    print_bank_amount = fields.Monetary(
        string="Print Bank Amount",
        compute="_compute_print_amounts",
        help="Gross Bank Amount before PF and ESI deductions when printing."
    )
    print_net_salary = fields.Monetary(
        string="Print Net Salary",
        compute="_compute_print_amounts",
        help="Net salary total for print report based on selected Cash/Bank options."
    )

    @api.depends('cash_print', 'bank_print', 'cash_payable', 'bank_payable', 'pf_deduction', 'esi_deduction', 'net_payable')
    def _compute_print_amounts(self):
        for slip in self:
            bank_gross = round((slip.bank_payable or 0.0) + (slip.pf_deduction or 0.0) + (slip.esi_deduction or 0.0), 2)
            slip.print_bank_amount = bank_gross if slip.bank_print else 0.0

            if slip.cash_print and slip.bank_print:
                slip.print_net_salary = round(slip.net_payable or 0.0, 2)
            elif slip.cash_print:
                slip.print_net_salary = round(slip.cash_payable or 0.0, 2)
            elif slip.bank_print:
                slip.print_net_salary = round(slip.bank_payable or 0.0, 2)
            else:
                slip.print_net_salary = 0.0

    def get_worked_days_line_amount(self, line):
        """
        Returns the worked days line amount based on selected cash_print / bank_print flags.
        - If both selected -> returns full line amount.
        - If line is Double Pay (only shown in Cash Print) -> returns full line amount.
        - Otherwise -> returns proportional split amount based on cash / bank ratio.
        """
        self.ensure_one()
        if not line:
            return 0.0
        amount = getattr(line, 'amount', 0.0) or 0.0
        if self.cash_print and self.bank_print:
            return amount

        code = (getattr(line, 'code', '') or '').upper()
        name = (getattr(line, 'name', '') or '').upper()

        # Double Pay is exclusive to Cash Print -> show full amount!
        if 'DOUBLE' in code or 'DOUBLE' in name:
            return amount

        employee = self.employee_id
        bank_amount = (employee.bank_amount if employee else 0.0) or 0.0
        cash_amount = (employee.cash_amount if employee else 0.0) or 0.0
        total_defined = bank_amount + cash_amount

        if not total_defined or amount == 0.0:
            return amount

        if self.cash_print:
            return round(amount * (cash_amount / total_defined), 2)
        elif self.bank_print:
            return round(amount * (bank_amount / total_defined), 2)

        return amount

    def get_filtered_worked_days_line_ids(self):
        """
        Returns worked_days_line_ids filtered by print flags.
        - Excludes Double Pay lines when ONLY Bank Print is selected.
        """
        self.ensure_one()
        lines = self.worked_days_line_ids.filtered(lambda l: l.code != 'OUT')
        if self.bank_print and not self.cash_print:
            lines = lines.filtered(lambda l: not ('DOUBLE' in (l.code or '').upper() or 'DOUBLE' in (l.name or '').upper()))
        return lines

    def get_worked_days_total_amount(self):
        """
        Returns total worked days earnings amount based on filtered worked days lines.
        """
        self.ensure_one()
        return sum(self.get_worked_days_line_amount(line) for line in self.get_filtered_worked_days_line_ids())

    def should_show_payslip_line(self, line):
        """
        Determines whether a salary line should be shown based on cash_print / bank_print.
        - Salary inputs (advance, travel, allowance, deduction, etc.): Shown ONLY in Bank Print or Both (hidden in Cash Print ONLY).
        - Double Pay lines: Shown ONLY in Cash Print or Both (hidden in Bank Print ONLY).
        - Cash line: Shown ONLY if cash_print is enabled.
        - Bank, ESI, PF lines: Shown ONLY if bank_print is enabled.
        """
        self.ensure_one()
        if not line:
            return False
        code = (getattr(line, 'code', '') or '').upper()
        name = (getattr(line, 'name', '') or '').upper()

        if code == 'CASH' or 'CASH' in name:
            return bool(self.cash_print)

        if code in ('BANK', 'ESI', 'PF', 'PF_DED') or any(k in name for k in ('BANK', 'ESI', 'PF')):
            return bool(self.bank_print)

        # Double Pay -> Show only in Cash Print or Both (hide in Bank Print ONLY)
        if 'DOUBLE' in code or 'DOUBLE' in name or 'DOUBLE PAY' in name:
            if self.bank_print and not self.cash_print:
                return False
            return True

        # Salary Inputs (Advance, Travel, Allowance, Deduction, Input) -> Show only in Bank Print or Both (hide in Cash Print ONLY)
        if any(k in name for k in ('ADVANCE', 'TRAVEL', 'ALLOWANCE', 'INPUT', 'DEDUCTION')) or any(k in code for k in ('ADV', 'TRAV', 'INPUT', 'DED')):
            if self.cash_print and not self.bank_print:
                return False
            return True

        return True

    def get_filtered_print_line_ids(self):
        """
        Returns payslip lines filtered by cash_print and bank_print options.
        """
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: l and getattr(l, 'appears_on_payslip', True))
        return lines.filtered(lambda l: self.should_show_payslip_line(l))

    def get_payslip_line_total(self, line):
        """
        Returns line total for payslip summary lines based on cash_print and bank_print options.
        """
        self.ensure_one()
        if not line:
            return 0.0
        code = (getattr(line, 'code', '') or '').upper()
        name = (getattr(line, 'name', '') or '').upper()
        total = getattr(line, 'total', 0.0) or 0.0

        if code == 'CASH' or 'CASH' in name:
            return self.cash_payable or 0.0
        elif code == 'BANK' or 'BANK' in name:
            return self.bank_payable or 0.0
        elif code == 'ESI' or 'ESI' in name:
            return self.esi_deduction or 0.0
        elif code in ('PF', 'PF_DED') or 'PF' in name:
            return self.pf_deduction or 0.0
        elif code == 'NET' or 'NET' in name or 'NET SALARY' in name:
            return self.print_net_salary or 0.0

        return total

    def _get_employee_bank_account_number(self):
        """
        Retrieves bank account number from bank_account_ids (or bank_account_id / primary_bank_account_id).
        """
        self.ensure_one()
        emp = self.employee_id
        if not emp:
            return 'N/A'
        
        # Check bank_account_ids (Many2many)
        if hasattr(emp, 'bank_account_ids') and emp.bank_account_ids:
            return emp.bank_account_ids[0].acc_number or 'N/A'
        
        # Check primary_bank_account_id
        if hasattr(emp, 'primary_bank_account_id') and emp.primary_bank_account_id:
            return emp.primary_bank_account_id.acc_number or 'N/A'

        # Check bank_account_id (Many2one fallback)
        if hasattr(emp, 'bank_account_id') and emp.bank_account_id:
            return emp.bank_account_id.acc_number or 'N/A'

        return 'N/A'

    def get_print_footer_text(self):
        """
        Returns the formatted footer text based on selected print flags.
        """
        self.ensure_one()
        emp_name = self.employee_id.legal_name or self.employee_id.name or ''
        acc_num = self._get_employee_bank_account_number()

        if self.cash_print and self.bank_print:
            amount_str = f"₹ {self.net_payable:,.2f}"
            if acc_num and acc_num != 'N/A':
                return f"To pay on {acc_num} of {emp_name}: {amount_str}"
            return f"To pay to {emp_name}: {amount_str}"

        elif self.cash_print:
            amount_str = f"₹ {self.cash_payable:,.2f}"
            return f"To pay in Cash to {emp_name}: {amount_str}"

        elif self.bank_print:
            amount_str = f"₹ {self.bank_payable:,.2f}"
            if acc_num and acc_num != 'N/A':
                return f"To pay on {acc_num} of {emp_name}: {amount_str}"
            return f"To pay to {emp_name}: {amount_str}"

        return ""

    def action_print_payslip(self):
        for payslip in self:
            if not payslip.cash_print and not payslip.bank_print:
                raise UserError(_("Please select at least one print option: Cash Print or Bank Print."))
        return super().action_print_payslip()
    esi_deduction = fields.Monetary(string="ESI Deduction", readonly=True)
    pf_deduction = fields.Monetary(string="PF Deduction", readonly=True)

    unpaid_amount = fields.Float(string="Unpaid Amount", readonly=True)
    unpaid_days = fields.Float(string="Unpaid Days", readonly=True)
    paid_amount = fields.Float(string="Paid Amount", readonly=True)
    paid_days = fields.Float(string="Paid Days", readonly=True)

    double_pay_days = fields.Float(string="Double Pay Days", readonly=True)
    sunday_worked_days = fields.Float(string="Sunday Worked Days", readonly=True)
    festival_worked_days = fields.Float(string="Festival Worked Days", readonly=True)
    lop_compensated_days = fields.Float(string="LOP Compensated", readonly=True)

    total_days_in_month = fields.Float(string="Total Days", readonly=True)
    total_working_days_in_month = fields.Float(string="Total Working Days", readonly=True)
    total_sundays_in_month = fields.Float(string="Total Sundays", readonly=True)
    total_festival_days_in_month = fields.Float(string="Total Festival Days", readonly=True)
    total_saturdays_in_month = fields.Float(string="Total Saturdays", readonly=True)

    regular_salary = fields.Monetary(string="Regular Salary", readonly=True)
    ot_amount = fields.Monetary(string="OT / Extra Salary", readonly=True)
    gross_salary = fields.Monetary(string="Gross Salary", readonly=True)
    net_payable = fields.Monetary(string="Net Payable", readonly=True)

    paid_festival_days = fields.Float(string="Paid Festival Days", readonly=True)
    required_attendance_days = fields.Float(string="Required Attendance Days", readonly=True)

    present_days = fields.Float(string="Present Days", readonly=True)
    absent_days_before_comp = fields.Float(string="Absent Days (Before Compensation)", readonly=True)
    total_ot_days = fields.Float(string="Total OT Days", readonly=True)
    # -------------------------------------------------------
    # Helpers
    # -------------------------------------------------------

    def _get_or_create_work_entry_type(self, code, name):
        wet = self.env['hr.work.entry.type'].search([('code', '=', code)], limit=1)
        if not wet:
            wet = self.env['hr.work.entry.type'].create({'name': name, 'code': code})
        return wet

    def _get_festival_dates(self, date_from, date_to):
        holidays = self.env[FESTIVAL_HOLIDAY_MODEL].search([
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ])
        return {h.date for h in holidays if h.date}

    def _build_attendance_map(self, employee, date_from, date_to):

        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', datetime.combine(date_from, time.min)),
            ('check_in', '<=', datetime.combine(date_to, time.max)),
        ])

        att_map = {}
        for att in attendances:
            if not att.check_in:
                continue
            work_date = fields.Datetime.context_timestamp(att, att.check_in).date()
            hours = att.worked_hours or 0.0
            att_map[work_date] = att_map.get(work_date, 0) + hours

        return att_map

    # -------------------------------------------------------
    # Main Compute
    # -------------------------------------------------------

    def compute_sheet(self):

        for payslip in self:

            employee = payslip.employee_id
            if not employee:
                continue

            version = payslip.version_id
            cal = version.resource_calendar_id if version else employee.resource_calendar_id
            group = cal.employee_group_rule if cal else False

            date_from = payslip.date_from
            date_to = payslip.date_to
            wage = payslip._get_contract_wage() or 0.0

            payslip.worked_days_line_ids.unlink()

            # ---------------------------------------------------
            # Calendar Days
            # ---------------------------------------------------
            all_days = []
            cur = date_from
            while cur <= date_to:
                all_days.append(cur)
                cur += timedelta(days=1)

            total_days = len(all_days)
            payslip.total_days_in_month = total_days
            per_day = wage / total_days if total_days else 0

            def is_sunday(d):
                return d.weekday() == 6

            festival_dates = self._get_festival_dates(date_from, date_to)
            sunday_days = {d for d in all_days if is_sunday(d)}

            # ---------------------------------------------------
            # Working Days per Group
            # ---------------------------------------------------

            if group == 'group_4':
                # All days working
                working_days = list(all_days)
            else:
                # Mon-Sat working
                working_days = [d for d in all_days if not is_sunday(d)]

            saturday_days = {d for d in all_days if d.weekday() == 5}

            # Festivals that fall on actual working days (Mon-Sat for Group 1-3, none for Group 4)
            if group == 'group_4':
                paid_festival_days_val = 0
            else:
                paid_festival_days_val = len(festival_dates & set(working_days))

            payslip.total_working_days_in_month = len(working_days)
            payslip.total_sundays_in_month = len(sunday_days)
            payslip.total_festival_days_in_month = len(festival_dates)
            payslip.total_saturdays_in_month = len(saturday_days)
            payslip.paid_festival_days = paid_festival_days_val
            payslip.required_attendance_days = len(working_days) - paid_festival_days_val

            # ---------------------------------------------------
            # Attendance Map
            # ---------------------------------------------------
            att_map = self._build_attendance_map(employee, date_from, date_to)
            attended_dates = set(att_map.keys())

            # ---------------------------------------------------
            # Attendance Classification
            # ---------------------------------------------------
            present_days = 0
            absent_days = 0

            for d in working_days:

                # Festival auto paid ONLY for Group 1-3
                if group in ('group_1', 'group_2', 'group_3', 'group_5') and d in festival_dates:
                    continue

                hrs = att_map.get(d, 0)

                if hrs >= 6:                                                              
                    present_days += 1
                elif 3 <= hrs < 6:
                    present_days += 0.5
                    absent_days += 0.5
                else:
                    absent_days += 1

            # ---------------------------------------------------
            # GROUP LOGIC
            # ---------------------------------------------------

            casual_leave = 0
            paid_leave_credit = 0
            sunday_worked = 0
            festival_worked = 0
            lop_compensated = 0
            double_pay_days = 0

            # GROUP 1
            if group == 'group_1':
                casual_leave = min(1, absent_days)
                absent_days -= casual_leave

            # GROUP 2 & 3
            if group in ('group_2', 'group_3'):

                if group == 'group_2':
                    paid_leave_credit = min(1, absent_days)
                    absent_days -= paid_leave_credit

                def day_fraction(d):
                    hrs = att_map.get(d, 0)
                    if hrs >= 6:
                        return 1.0
                    elif hrs >= 3:
                        return 0.5
                    return 0.0

                sunday_worked = sum(day_fraction(d) for d in sunday_days
                                    if d in attended_dates and d not in festival_dates)
                festival_worked = sum(day_fraction(d) for d in festival_dates if d in attended_dates)

                total_ot = sunday_worked + festival_worked

                lop_compensated = min(absent_days, total_ot)
                absent_days -= lop_compensated

                double_pay_days = total_ot - lop_compensated

            # GROUP 4
            if group == 'group_4':
                # No leave, no compensation, no OT
                sunday_worked = 0
                festival_worked = 0
                lop_compensated = 0
                double_pay_days = 0

            final_lop = absent_days

            # ---------------------------------------------------
            # Salary
            # ---------------------------------------------------

            unpaid_amount = round(final_lop * per_day, 2)
            extra_ot_amount = round(double_pay_days * per_day, 2)

            regular_salary_val = round(wage - unpaid_amount, 2)
            gross_salary_val = round(regular_salary_val + extra_ot_amount, 2)

            # ---------------------------------------------------
            # Bank & Cash Split Logic
            # ---------------------------------------------------

            bank_amount = employee.bank_amount or 0.0
            cash_amount = employee.cash_amount or 0.0
            
            # If employee defined split
            if bank_amount or cash_amount:

                total_defined = bank_amount + cash_amount

                if total_defined == 0:
                    bank_final = 0
                    cash_final = 0
                    pf = 0.0
                    esi = 0.0
                else:
                    # LOP deducted proportionally from bank and cash
                    per_day_bank = bank_amount / total_days if total_days else 0
                    per_day_cash = cash_amount / total_days if total_days else 0

                    bank_lop_deduction = round(final_lop * per_day_bank, 2)
                    cash_lop_deduction = round(final_lop * per_day_cash, 2)
                    
                    salary_advance   = sum(l.amount for l in payslip.input_line_ids if l.code == 'SAL-ADV')
                    salary_deduction = sum(l.amount for l in payslip.input_line_ids if l.code == 'SAL-ADV-DED')

                    bank_after_lop = bank_amount - bank_lop_deduction
                    
                    cash_after_lop = cash_amount - cash_lop_deduction + extra_ot_amount
                   
                    
                    # PF = 12% of 70% of bank after LOP
                    # ESI = 0.75% of PF base
                    pf_base = round(bank_after_lop * 0.70, 2)
                    pf = round(pf_base * 0.12, 2)
                    esi = round(bank_after_lop * 0.0075, 2)
                    _logger.debug("pf_base = %s; pf = %s; esi = %s", pf_base, pf, esi)
                    # Subtract employee deductions (PF and ESI) from bank payable.
                    bank_final = round(bank_after_lop - pf - esi + salary_advance - salary_deduction, 2)
                    _logger.debug("bank_final = %s", bank_final)
                    cash_final = round(cash_after_lop, 2)

            else:
                # No split defined → entire salary to bank
                pf_base = round(gross_salary_val * 0.70, 2)
                pf = round(pf_base * 0.12, 2)
                esi = round(pf_base * 0.0075, 2)
                # Subtract employee deductions (PF and ESI) from bank payable.
                bank_final = round(gross_salary_val - pf - esi, 2)
                cash_final = 0

            # Net payable is the sum of net bank and net cash payables
            net_payable_val = round(bank_final + cash_final, 2)

            # Store values
            payslip.bank_payable = round(bank_final, 2)
            payslip.cash_payable = round(cash_final, 2)
            payslip.esi_deduction = esi
            payslip.pf_deduction = pf

            payslip.unpaid_days = final_lop
            payslip.paid_days = present_days + casual_leave + paid_leave_credit + lop_compensated + double_pay_days
            payslip.unpaid_amount = unpaid_amount
            # Total Paid Amount = net paid to employee (gross payables - employee deductions).
            payslip.paid_amount = net_payable_val
            payslip.regular_salary = regular_salary_val
            payslip.ot_amount = extra_ot_amount
            payslip.gross_salary = gross_salary_val
            payslip.net_payable = net_payable_val
            payslip.double_pay_days = double_pay_days
            payslip.lop_compensated_days = lop_compensated
            payslip.sunday_worked_days = sunday_worked
            payslip.festival_worked_days = festival_worked
            payslip.present_days = present_days
            payslip.absent_days_before_comp = lop_compensated + final_lop
            payslip.total_ot_days = sunday_worked + festival_worked

            # ---------------------------------------------------
            # Build Lines
            # ---------------------------------------------------
            def wet(code, name):
                return self._get_or_create_work_entry_type(code, name).id

            lines = []

            if present_days:
                lines.append({
                    'name': 'Attendance',
                    'code': 'WORK100',
                    'number_of_days': present_days,
                    'number_of_hours': present_days * 8,
                    'amount': round(present_days * per_day, 2),
                    'work_entry_type_id': wet('WORK100', 'Attendance'),
                })

            if group != 'group_4':
                lines.append({
                    'name': 'Paid Sunday',
                    'code': 'SUNDAY',
                    'number_of_days': len(sunday_days),
                    'number_of_hours': len(sunday_days) * 8,
                    'amount': round(len(sunday_days) * per_day, 2),
                    'work_entry_type_id': wet('SUNDAY', 'Paid Sunday'),
                })

                if festival_dates:
                    lines.append({
                        'name': 'Paid Festival',
                        'code': 'FESTIVAL',
                        'number_of_days': len(festival_dates),
                        'number_of_hours': len(festival_dates) * 8,
                        'amount': round(len(festival_dates) * per_day, 2),
                        'work_entry_type_id': wet('FESTIVAL', 'Paid Festival'),
                    })

            if casual_leave:
                lines.append({
                    'name': 'Paid Leave',
                    'code': 'PAIDLEAVE',
                    'number_of_days': casual_leave,
                    'number_of_hours': casual_leave * 8,
                    'amount': round(casual_leave * per_day, 2),
                    'work_entry_type_id': wet('PAIDLEAVE', 'Paid Leave'),
                })

            if paid_leave_credit:
                lines.append({
                    'name': 'Paid Leave (Group 2)',
                    'code': 'PAIDLEAVE',
                    'number_of_days': paid_leave_credit,
                    'number_of_hours': paid_leave_credit * 8,
                    'amount': round(paid_leave_credit * per_day, 2),
                    'work_entry_type_id': wet('PAIDLEAVE', 'Paid Leave'),
                })

            if lop_compensated:
                lines.append({
                    'name': 'LOP Compensated',
                    'code': 'LOPCOMP',
                    'number_of_days': lop_compensated,
                    'number_of_hours': lop_compensated * 8,
                    'amount': round(lop_compensated * per_day, 2),
                    'work_entry_type_id': wet('LOPCOMP', 'LOP Compensated'),
                })

            if double_pay_days:
                lines.append({
                    'name': 'Double Pay (OT)',
                    'code': 'DOUBLEPAY',
                    'number_of_days': double_pay_days,
                    'number_of_hours': double_pay_days * 8,
                    'amount': round(double_pay_days * per_day, 2),
                    'work_entry_type_id': wet('DOUBLEPAY', 'Double Pay'),
                })

            if final_lop:
                lines.append({
                    'name': 'Absent / LOP',
                    'code': 'LOP',
                    'number_of_days': final_lop,
                    'number_of_hours': final_lop * 8,
                    'amount': 0.0,
                    'work_entry_type_id': wet('LOP', 'Unpaid'),
                })

            payslip.worked_days_line_ids = [(0, 0, v) for v in lines]

        return super().compute_sheet()
