# models/hr_payslip.py
from odoo import models, fields
from datetime import timedelta, time, datetime

FESTIVAL_HOLIDAY_MODEL = 'hr.festival.holiday'


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # ─────────────────────────────────────────
    # Summary Fields
    # ─────────────────────────────────────────
    unpaid_amount = fields.Float(string="Unpaid Amount", readonly=True)
    unpaid_days = fields.Float(string="Unpaid Days", readonly=True)
    paid_days = fields.Float(string="Paid Days", readonly=True)
    paid_amount = fields.Float(string="Paid Amount", readonly=True)
    total_days_in_month = fields.Float(string="Total Days in Month", readonly=True)
    total_working_days_in_month = fields.Float(string="Total Working Days", readonly=True)

    double_pay_days = fields.Float(string="Double Pay Days", readonly=True)
    sunday_worked_days = fields.Float(string="Sunday Worked Days", readonly=True)
    festival_worked_days = fields.Float(string="Festival Worked Days", readonly=True)
    lop_compensated_days = fields.Float(string="LOP Compensated", readonly=True)

    total_saturdays_in_month = fields.Float(string="Total Saturdays", readonly=True)
    total_sundays_in_month = fields.Float(string="Total Sundays", readonly=True)
    total_festival_days_in_month = fields.Float(string="Total Festival Days", readonly=True)

    # ─────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────
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

    def _build_attendance_map(self, employee, date_from, date_to, version):
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', datetime.combine(date_from, time.min)),
            ('check_out', '<=', datetime.combine(date_to, time.max)),
        ])
        att_map = {}
        for att in attendances:
            if not att.check_in or not att.check_out:
                continue
            work_date = att.check_in.date()
            hours = (att.check_out - att.check_in).total_seconds() / 3600
            att_map[work_date] = max(att_map.get(work_date, 0), hours)
        return att_map

    # ─────────────────────────────────────────
    # Main Compute
    # ─────────────────────────────────────────
    def compute_sheet(self):

        for payslip in self:
            version = payslip.version_id
            employee = payslip.employee_id

            if not employee:
                continue

            cal = version.resource_calendar_id if version else employee.resource_calendar_id
            group = cal.employee_group_rule if cal else False

            date_from = payslip.date_from
            date_to = payslip.date_to

            wage = payslip._get_contract_wage() or 0.0

            payslip.worked_days_line_ids.unlink()

            # ────────────────────────
            # Calendar Setup
            # ────────────────────────
            all_days = []
            cur = date_from
            while cur <= date_to:
                all_days.append(cur)
                cur += timedelta(days=1)

            total_calendar_days = len(all_days)
            payslip.total_days_in_month = total_calendar_days

            per_day = wage / total_calendar_days if total_calendar_days else 0

            def is_sunday(d):
                return d.weekday() == 6

            festival_dates = self._get_festival_dates(date_from, date_to)

            if group == 'group_4':
                working_days = list(all_days)
                sunday_days = set()
            else:
                working_days = [d for d in all_days if not is_sunday(d)]
                sunday_days = {d for d in all_days if is_sunday(d)}

            payslip.total_working_days_in_month = len(working_days)

            att_map = self._build_attendance_map(employee, date_from, date_to, version)
            attended_dates = set(att_map.keys())

            sundays_worked = sunday_days & attended_dates
            festivals_worked = festival_dates & attended_dates

            # ────────────────────────
            # Attendance Classification
            # ────────────────────────
            full_days = 0
            half_days = 0
            absent_days = 0

            for d in working_days:

                # Festival paid day (Group 1-3)
                if group in ('group_1', 'group_2', 'group_3') and d in festival_dates:
                    continue

                hrs = att_map.get(d, 0)

                if hrs >= 7:
                    full_days += 1
                elif hrs >= 3:
                    half_days += 0.5
                else:
                    absent_days += 1

            # ────────────────────────
            # Group Rules
            # ────────────────────────
            casual_leave_credit = 0
            paid_leave_credit = 0

            if group == 'group_1':
                casual_leave_credit = min(1, absent_days)
                absent_days -= casual_leave_credit

            if group == 'group_2':
                paid_leave_credit = min(1, absent_days)
                absent_days -= paid_leave_credit

            sunday_comp = 0
            fest_comp = 0
            extra_sunday = 0
            extra_fest = 0

            if group in ('group_2', 'group_3'):
                sunday_comp = min(absent_days, len(sundays_worked))
                absent_days -= sunday_comp

                fest_comp = min(absent_days, len(festivals_worked))
                absent_days -= fest_comp

                extra_sunday = max(0, len(sundays_worked) - sunday_comp)
                extra_fest = max(0, len(festivals_worked) - fest_comp)

            final_lop = absent_days
            double_pay_days = extra_sunday + extra_fest

            # ────────────────────────
            # Final Salary Logic
            # ────────────────────────
            unpaid_amount = round(final_lop * per_day, 2)
            net_salary = round(wage - unpaid_amount, 2)

            payslip.unpaid_days = final_lop
            payslip.unpaid_amount = unpaid_amount
            payslip.paid_amount = net_salary
            payslip.double_pay_days = double_pay_days
            payslip.sunday_worked_days = len(sundays_worked)
            payslip.festival_worked_days = len(festivals_worked)
            payslip.lop_compensated_days = sunday_comp
            payslip.total_sundays_in_month = len(sunday_days)
            payslip.total_festival_days_in_month = len(festival_dates)

            # ────────────────────────
            # Build Lines
            # ────────────────────────
            def wet(code, name):
                return self._get_or_create_work_entry_type(code, name).id

            lines = []

            if full_days:
                lines.append({
                    'name': 'Present (Full Day)',
                    'code': 'WORK100',
                    'number_of_days': full_days,
                    'number_of_hours': full_days * 8,
                    'amount': round(full_days * per_day, 2),
                    'work_entry_type_id': wet('WORK100', 'Attendance'),
                })

            if final_lop:
                lines.append({
                    'name': 'Absent / LOP',
                    'code': 'LEAVE90',
                    'number_of_days': final_lop,
                    'number_of_hours': final_lop * 8,
                    'amount': unpaid_amount,
                    'work_entry_type_id': wet('LEAVE90', 'Unpaid / LOP'),
                })

            if casual_leave_credit:
                lines.append({
                    'name': 'Casual Leave',
                    'code': 'CASUALLEAVE',
                    'number_of_days': casual_leave_credit,
                    'number_of_hours': casual_leave_credit * 8,
                    'amount': round(casual_leave_credit * per_day, 2),
                    'work_entry_type_id': wet('CASUALLEAVE', 'Casual Leave'),
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

            if double_pay_days:
                lines.append({
                    'name': 'Double Pay (Sunday/Festival)',
                    'code': 'DOUBLEPAY',
                    'number_of_days': double_pay_days,
                    'number_of_hours': double_pay_days * 8,
                    'amount': round(double_pay_days * per_day, 2),
                    'work_entry_type_id': wet('DOUBLEPAY', 'Double Pay'),
                })

            payslip.worked_days_line_ids = [(0, 0, v) for v in lines]

        return super().compute_sheet()