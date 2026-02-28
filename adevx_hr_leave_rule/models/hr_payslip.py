# models/hr_payslip.py
from odoo import models, fields
from datetime import timedelta, datetime, time
import logging

_logger = logging.getLogger(__name__)

FESTIVAL_HOLIDAY_MODEL = 'hr.festival.holiday'


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

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
            work_date = att.check_in.date()
            hours = att.worked_hours or 0.0
            att_map[work_date] = max(att_map.get(work_date, 0), hours)

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

            payslip.total_working_days_in_month = len(working_days)
            payslip.total_sundays_in_month = len(sunday_days)
            payslip.total_festival_days_in_month = len(festival_dates)
            payslip.total_saturdays_in_month = len(working_days) - len(sunday_days) - len(festival_dates)

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
                if group in ('group_1', 'group_2', 'group_3') and d in festival_dates:
                    continue

                hrs = att_map.get(d, 0)

                if hrs >= 6:
                    present_days += 1
                elif 4 <= hrs < 6:
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

                sunday_worked = len(sunday_days & attended_dates)
                festival_worked = len(festival_dates & attended_dates)

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
            net_salary = round(wage - unpaid_amount, 2)

            payslip.unpaid_days = final_lop
            payslip.paid_days = present_days + casual_leave + paid_leave_credit + lop_compensated + double_pay_days
            payslip.unpaid_amount = unpaid_amount
            payslip.paid_amount = net_salary
            payslip.double_pay_days = double_pay_days
            payslip.lop_compensated_days = lop_compensated
            payslip.sunday_worked_days = sunday_worked
            payslip.festival_worked_days = festival_worked

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
                    'name': 'Casual Leave',
                    'code': 'CASUAL',
                    'number_of_days': casual_leave,
                    'number_of_hours': casual_leave * 8,
                    'amount': round(casual_leave * per_day, 2),
                    'work_entry_type_id': wet('CASUAL', 'Casual Leave'),
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