# models/hr_payslip.py
from odoo import models, fields
from datetime import timedelta, time, datetime

FESTIVAL_HOLIDAY_MODEL = 'hr.festival.holiday'
import logging
_logger = logging.getLogger(__name__)

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

            # ----------------------------
            # Calendar
            # ----------------------------
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
            working_days = [d for d in all_days if not is_sunday(d)]

            payslip.total_working_days_in_month = len(working_days)
            payslip.total_sundays_in_month = len(sunday_days)
            payslip.total_festival_days_in_month = len(festival_dates)

            att_map = self._build_attendance_map(employee, date_from, date_to, version)
            attended_dates = set(att_map.keys())

            # ----------------------------
            # Count
            # ----------------------------
            attendance_present = 0
            absent_days = 0

            for d in working_days:

                if d in festival_dates:
                    continue  # Festival automatically paid

                hrs = att_map.get(d, 0)

                if hrs >= 6:
                    attendance_present += 1
                else:
                    _logger.warning("__________________________Absent: %s", d)
                    absent_days += 1

            # Group 1 Casual Leave
            casual_leave = 0
            if group == 'group_1':
                casual_leave = min(1, absent_days)
                absent_days -= casual_leave

            final_lop = absent_days

            # ----------------------------
            # Salary Logic
            # ----------------------------
            unpaid_amount = round(final_lop * per_day, 2)
            net_salary = round(wage - unpaid_amount, 2)

            payslip.unpaid_days = final_lop
            payslip.unpaid_amount = unpaid_amount
            payslip.paid_amount = net_salary

            # ----------------------------
            # Build Lines
            # ----------------------------
            def wet(code, name):
                return self._get_or_create_work_entry_type(code, name).id

            lines = []

            # Attendance
            if attendance_present:
                lines.append({
                    'name': 'Attendance (Mon-Sat)',
                    'code': 'WORK100',
                    'number_of_days': attendance_present,
                    'number_of_hours': attendance_present * 8,
                    'amount': round(attendance_present * per_day, 2),
                    'work_entry_type_id': wet('WORK100', 'Attendance'),
                })

            # Paid Sundays
            lines.append({
                'name': 'Paid Sunday',
                'code': 'SUNDAY',
                'number_of_days': len(sunday_days),
                'number_of_hours': len(sunday_days) * 8,
                'amount': round(len(sunday_days) * per_day, 2),
                'work_entry_type_id': wet('SUNDAY', 'Paid Sunday'),
            })

            # Paid Festival
            fest_count = len(festival_dates)
            if fest_count:
                lines.append({
                    'name': 'Paid Festival',
                    'code': 'FESTIVAL',
                    'number_of_days': fest_count,
                    'number_of_hours': fest_count * 8,
                    'amount': round(fest_count * per_day, 2),
                    'work_entry_type_id': wet('FESTIVAL', 'Paid Festival'),
                })

            # Casual Leave
            if casual_leave:
                lines.append({
                    'name': 'Casual Leave',
                    'code': 'CASUAL',
                    'number_of_days': casual_leave,
                    'number_of_hours': casual_leave * 8,
                    'amount': round(casual_leave * per_day, 2),
                    'work_entry_type_id': wet('CASUAL', 'Casual Leave'),
                })

            # LOP
            if final_lop:
                lines.append({
                    'name': 'Absent / LOP',
                    'code': 'LOP',
                    'number_of_days': final_lop,
                    'number_of_hours': final_lop * 8,
                    'amount': unpaid_amount,
                    'work_entry_type_id': wet('LOP', 'Unpaid'),
                })

            payslip.worked_days_line_ids = [(0, 0, v) for v in lines]

        return super().compute_sheet()