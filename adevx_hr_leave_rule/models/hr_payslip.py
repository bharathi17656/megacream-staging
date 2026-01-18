# models/hr_payslip.py
from odoo import models, fields, api
from datetime import timedelta, time , datetime
import math
import calendar
import logging
 

_logger = logging.getLogger(__name__)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    unpaid_amount = fields.Float(string="Unpaid Amount", readonly=True)
    unpaid_days = fields.Float(string="Unpaid Days", readonly=True)
    paid_days = fields.Float(string="Paid Days", readonly=True)
    paid_amount = fields.Float(string="Paid Amount", readonly=True)
    total_days_in_month = fields.Float(string="Total Days in Month", readonly=True)
    total_working_days_in_month = fields.Float(string="Total Working Days in Month", readonly=True)

    def compute_sheet(self):
        WorkEntryType = self.env['hr.work.entry.type']
        Attendance = self.env['hr.attendance']
        Leave = self.env['hr.leave']

        def _get_or_create(code, name):
            rec = WorkEntryType.search([('code', '=', code)], limit=1)
            if not rec:
                rec = WorkEntryType.create({'name': name, 'code': code})
            return rec

       

        for payslip in self:
            contract = payslip.version_id
            employee = contract.employee_id if contract else payslip.employee_id
            if not contract or not employee:
                continue

         
            # -------------------------------------------------------------------
            # CASE 1: work_entry_source == 'calendar'
            # -------------------------------------------------------------------
            
            if contract.work_entry_source == 'calendar':
            
                calendar = contract.resource_calendar_id
                date_from = payslip.date_from
                date_to = payslip.date_to
            
                payslip.worked_days_line_ids.unlink()
            
                # -------------------------------------------------------
                # 1️⃣ WORKING DAYS FROM RESOURCE CALENDAR
                # -------------------------------------------------------
                def _is_working_day(cal, day):
                    start = datetime.combine(day, time.min)
                    end = datetime.combine(day, time.max)
                    return cal.get_work_hours_count(start, end) > 0
            
                working_days = []
                cur = date_from
                while cur <= date_to:
                    if _is_working_day(calendar, cur):
                        working_days.append(cur)
                    cur += timedelta(days=1)
            
                expected_working_days = len(working_days)
                payslip.total_working_days_in_month = expected_working_days
            
                # -------------------------------------------------------
                # 2️⃣ WORK ENTRIES (DAY-WISE MAP)
                # -------------------------------------------------------
                work_entries = self.env['hr.work.entry'].search([
                    ('employee_id', '=', employee.id),
                    ('date', '>=', date_from),
                    ('date', '<=', date_to),
                ])
            
                attendance_days = set()
                half_days = set()
                casual_days = set()
                sick_days = set()
                unpaid_leave_days = set()
            
                for we in work_entries:
                    d = we.date
            
                    if d not in working_days:
                        continue
            
                    # ❌ Ignore outside contract
                    if contract.date_start and d < contract.date_start:
                        continue
                    if contract.date_end and d > contract.date_end:
                        continue
            
                    code = we.work_entry_type_id.code.upper()
            
                    if code in ('WORK100', 'ATTENDANCE'):
                        attendance_days.add(d)
            
                    elif code in ('HALF', 'HALFDAY'):
                        half_days.add(d)
            
                    elif code == 'CASUAL':
                        casual_days.add(d)
            
                    elif code == 'SICK':
                        sick_days.add(d)
            
                    elif code in ('LEAVE90', 'UNPAID', 'LOP'):
                        unpaid_leave_days.add(d)
            
                # -------------------------------------------------------
                # 3️⃣ OUT OF CONTRACT DAYS
                # -------------------------------------------------------
                out_days = {
                    d for d in working_days
                    if (contract.date_start and d < contract.date_start)
                    or (contract.date_end and d > contract.date_end)
                }
            
                # -------------------------------------------------------
                # 4️⃣ AUTO UNPAID (ABSENT DAYS)
                # -------------------------------------------------------
                unpaid_auto_days = set()
            
                for d in working_days:
                    if d in out_days:
                        continue
                    if d in attendance_days or d in half_days:
                        continue
                    if d in casual_days or d in sick_days or d in unpaid_leave_days:
                        continue
                    unpaid_auto_days.add(d)
            
                # -------------------------------------------------------
                # 5️⃣ FINAL COUNTS (BALANCED)
                # -------------------------------------------------------
                paid_days = (
                    len(attendance_days)
                    + (len(half_days) * 0.5)
                    + len(casual_days)
                    + len(sick_days)
                )
            
                unpaid_days = (
                    len(unpaid_leave_days)
                    + len(unpaid_auto_days)
                )
            
                out_days_total = len(out_days)
            
                payslip.paid_days = paid_days
                payslip.unpaid_days = unpaid_days
            
                # SAFETY CHECK
                if round(paid_days + unpaid_days + out_days_total, 2) != round(expected_working_days, 2):
                    _logger.warning(
                        "Payroll mismatch: Paid(%s) + Unpaid(%s) + Out(%s) != Working(%s)",
                        paid_days, unpaid_days, out_days_total, expected_working_days
                    )
            
                # -------------------------------------------------------
                # 6️⃣ AMOUNT CALCULATION
                # -------------------------------------------------------
                per_day_cost = contract.wage / expected_working_days if expected_working_days else 0
            
                payslip.paid_amount = paid_days * per_day_cost
                payslip.unpaid_amount = (unpaid_days + out_days_total) * per_day_cost
            
                # -------------------------------------------------------
                # 7️⃣ WORKED DAYS LINES (UI)
                # -------------------------------------------------------
                worked_lines = []
            
                if attendance_days:
                    worked_lines.append({
                        'name': 'Attendance',
                        'code': 'WORK100',
                        'number_of_days': len(attendance_days),
                        'number_of_hours': len(attendance_days) * 8,
                        'work_entry_type_id': _get_or_create('WORK100', 'Attendance').id,
                    })
            
                if half_days:
                    worked_lines.append({
                        'name': 'Half Day Attendance',
                        'code': 'HALF',
                        'number_of_days': len(half_days) * 0.5,
                        'number_of_hours': len(half_days) * 4,
                        'work_entry_type_id': _get_or_create('HALF', 'Half Day Attendance').id,
                    })
            
                if casual_days:
                    worked_lines.append({
                        'name': 'Casual Leave',
                        'code': 'CASUAL',
                        'number_of_days': len(casual_days),
                        'number_of_hours': len(casual_days) * 8,
                        'work_entry_type_id': _get_or_create('CASUAL', 'Casual Leave').id,
                    })
            
                if sick_days:
                    worked_lines.append({
                        'name': 'Sick Leave',
                        'code': 'SICK',
                        'number_of_days': len(sick_days),
                        'number_of_hours': len(sick_days) * 8,
                        'work_entry_type_id': _get_or_create('SICK', 'Sick Leave').id,
                    })
            
                if unpaid_days:
                    worked_lines.append({
                        'name': 'Unpaid / LOP',
                        'code': 'LEAVE90',
                        'number_of_days': unpaid_days,
                        'number_of_hours': unpaid_days * 8,
                        'work_entry_type_id': _get_or_create('LEAVE90', 'Unpaid').id,
                    })
            
                if out_days_total:
                    worked_lines.append({
                        'name': 'Out of Contract',
                        'code': 'OUT',
                        'number_of_days': out_days_total,
                        'number_of_hours': out_days_total * 8,
                        'work_entry_type_id': _get_or_create('OUT', 'Out of Contract').id,
                    })
            
                payslip.worked_days_line_ids = [(0, 0, vals) for vals in worked_lines]
            
                continue

         
            # -------------------------------------------------------------------
            # CASE 2: If NOT calendar → CUSTOM attendance based payroll
            # -------------------------------------------------------------------
            
            if contract.work_entry_source != 'calendar':
            
                calendar = contract.resource_calendar_id
                date_from = payslip.date_from
                date_to = payslip.date_to
            
                payslip.worked_days_line_ids.unlink()
            
                # -------------------------------------------------------
                # 1️⃣ WORKING DAYS FROM CALENDAR
                # -------------------------------------------------------
                def _is_working_day(cal, day):
                    start = datetime.combine(day, time.min)
                    end = datetime.combine(day, time.max)
                    return cal.get_work_hours_count(start, end) > 0
            
                working_days = []
                cur = date_from
                while cur <= date_to:
                    if _is_working_day(calendar, cur):
                        working_days.append(cur)
                    cur += timedelta(days=1)
            
                expected_working_days = len(working_days)
                payslip.total_working_days_in_month = expected_working_days
            
                # -------------------------------------------------------
                # 2️⃣ LEAVES (DAY-WISE)
                # -------------------------------------------------------
                leave_dates_paid = set()
                leave_dates_unpaid = set()
            
                leaves = Leave.search([
                    ('employee_id', '=', employee.id),
                    ('state', 'in', ('validate', 'approved')),
                    ('request_date_from', '<=', date_to),
                    ('request_date_to', '>=', date_from),
                ])
            
                for lv in leaves:
                    cur = max(lv.request_date_from, date_from)
                    end = min(lv.request_date_to, date_to)
            
                    while cur <= end:
                        if cur in working_days:
                            if lv.holiday_status_id.unpaid:
                                leave_dates_unpaid.add(cur)
                            else:
                                leave_dates_paid.add(cur)
                        cur += timedelta(days=1)
            
                paid_leave_days = len(leave_dates_paid)
                unpaid_leave_days = len(leave_dates_unpaid)
            
                # -------------------------------------------------------
                # 3️⃣ ATTENDANCE (DAY-WISE, CONTRACT SAFE)
                # -------------------------------------------------------
                attendances = Attendance.search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', datetime.combine(date_from, time.min)),
                    ('check_out', '<=', datetime.combine(date_to, time.max)),
                ])
            
                attendance_map = {}  # date → max hours
            
                for att in attendances:
                    if not att.check_in or not att.check_out:
                        continue
            
                    work_date = att.check_in.date()
            
                    # ❌ Ignore outside working days
                    if work_date not in working_days:
                        continue
            
                    # ❌ Ignore outside contract
                    if contract.date_start and work_date < contract.date_start:
                        continue
                    if contract.date_end and work_date > contract.date_end:
                        continue
            
                    hours = (att.check_out - att.check_in).total_seconds() / 3600
                    attendance_map[work_date] = max(attendance_map.get(work_date, 0), hours)
            
                full_days = 0.0
                half_days = 0.0
            
                for hrs in attendance_map.values():
                    if hrs >= 7:
                        full_days += 1
                    elif hrs >= 3:
                        half_days += 0.5
            
                # -------------------------------------------------------
                # 4️⃣ OUT OF CONTRACT DAYS
                # -------------------------------------------------------
                out_days = [
                    d for d in working_days
                    if (contract.date_start and d < contract.date_start)
                    or (contract.date_end and d > contract.date_end)
                ]
                out_day_count = len(out_days)
            
                # -------------------------------------------------------
                # 5️⃣ AUTO UNPAID (ABSENT / HALF BALANCE)
                # -------------------------------------------------------
                unpaid_auto_days = 0.0
            
                for d in working_days:
                    if d in out_days:
                        continue
                    if d in leave_dates_paid or d in leave_dates_unpaid:
                        continue
            
                    if d not in attendance_map:
                        unpaid_auto_days += 1
                    else:
                        hrs = attendance_map[d]
                        if 3 <= hrs < 7:
                            unpaid_auto_days += 0.5
            
                # -------------------------------------------------------
                # 6️⃣ FINAL COUNTS (BALANCED)
                # -------------------------------------------------------
                paid_days = full_days + half_days + paid_leave_days
                unpaid_days = unpaid_leave_days + unpaid_auto_days
                out_days_total = out_day_count
            
                payslip.paid_days = paid_days
                payslip.unpaid_days = unpaid_days
            
                if round(paid_days + unpaid_days + out_days_total, 2) != round(expected_working_days, 2):
                    _logger.warning(
                        "Payroll mismatch: Paid(%s) + Unpaid(%s) + Out(%s) != Working(%s)",
                        paid_days, unpaid_days, out_days_total, expected_working_days
                    )
            
                # -------------------------------------------------------
                # 7️⃣ AMOUNTS
                # -------------------------------------------------------
                per_day_cost = contract.wage / expected_working_days if expected_working_days else 0
            
                payslip.paid_amount = paid_days * per_day_cost
                payslip.unpaid_amount = (unpaid_days + out_days_total) * per_day_cost
            
                # -------------------------------------------------------
                # 8️⃣ WORKED DAYS LINES (UI)
                # -------------------------------------------------------
                worked_lines = []
            
                if full_days:
                    worked_lines.append({
                        'name': 'Attendance',
                        'code': 'WORK100',
                        'number_of_days': full_days,
                        'number_of_hours': full_days * 8,
                        'work_entry_type_id': _get_or_create('WORK100', 'Attendance').id,
                    })
            
                if half_days:
                    worked_lines.append({
                        'name': 'Half Day Attendance',
                        'code': 'HALF',
                        'number_of_days': half_days,
                        'number_of_hours': half_days * 4,
                        'work_entry_type_id': _get_or_create('HALF', 'Half Day Attendance').id,
                    })
            
                if unpaid_days:
                    worked_lines.append({
                        'name': 'Unpaid / LOP',
                        'code': 'LEAVE90',
                        'number_of_days': unpaid_days,
                        'number_of_hours': unpaid_days * 8,
                        'work_entry_type_id': _get_or_create('LEAVE90', 'Unpaid').id,
                    })
            
                if out_days_total:
                    worked_lines.append({
                        'name': 'Out of Contract',
                        'code': 'OUT',
                        'number_of_days': out_days_total,
                        'number_of_hours': out_days_total * 8,
                        'work_entry_type_id': _get_or_create('OUT', 'Out of Contract').id,
                    })
            
                payslip.worked_days_line_ids = [(0, 0, vals) for vals in worked_lines]

        return super(HrPayslip, self).compute_sheet()
