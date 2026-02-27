# models/hr_payslip.py
from odoo import models, fields, api
from datetime import timedelta, time, datetime, date
import math
import calendar
import logging

_logger = logging.getLogger(__name__)

FESTIVAL_HOLIDAY_MODEL = 'hr.festival.holiday'


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    unpaid_amount = fields.Float(string="Unpaid Amount", readonly=True)
    unpaid_days = fields.Float(string="Unpaid Days", readonly=True)
    paid_days = fields.Float(string="Paid Days", readonly=True)
    paid_amount = fields.Float(string="Paid Amount", readonly=True)
    total_days_in_month = fields.Float(string="Total Days in Month", readonly=True)
    total_working_days_in_month = fields.Float(string="Total Working Days in Month", readonly=True)

    # Group-Based summary fields
    double_pay_days = fields.Float(string="Double Pay Days", readonly=True)
    sunday_worked_days = fields.Float(string="Sunday Worked Days (Compensation)", readonly=True)
    festival_worked_days = fields.Float(string="Festival Worked Days", readonly=True)
    lop_compensated_days = fields.Float(string="LOP Compensated (Sunday Work)", readonly=True)

    def compute_sheet(self):
        WorkEntryType = self.env['hr.work.entry.type']
        Attendance = self.env['hr.attendance']
        Leave = self.env['hr.leave']

        def _get_or_create(code, name):
            rec = WorkEntryType.search([('code', '=', code)], limit=1)
            if not rec:
                rec = WorkEntryType.create({'name': name, 'code': code})
            return rec

        def _get_festival_dates(date_from, date_to):
            """Return set of festival holiday dates within given period."""
            holidays = self.env[FESTIVAL_HOLIDAY_MODEL].search([
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ])
            return set(h.date for h in holidays)

        def _is_working_day_cal(cal, day):
            start = datetime.combine(day, time.min)
            end = datetime.combine(day, time.max)
            return cal.get_work_hours_count(start, end) > 0

        def _is_sunday(d):
            return d.weekday() == 6  # Monday=0, Sunday=6

        for payslip in self:
            employee = payslip.employee_id
            # In Odoo 19 payroll, wage lives on the contract (payslip.contract_id)
            # but the working schedule (resource.calendar) is on hr.employee directly.
            contract = payslip.contract_id  # may be False/empty in some flows
            if not employee:
                continue

            # Working Schedule comes from employee (Odoo 19 style)
            cal = employee.resource_calendar_id
            date_from = payslip.date_from
            date_to = payslip.date_to

            # Group rule is set on the Working Schedule
            group = cal.employee_group_rule if cal else False

            # Wage: prefer contract wage, fallback to employee's contract via sudo
            wage = 0.0
            if contract and hasattr(contract, 'wage'):
                wage = contract.wage or 0.0
            elif employee.contract_id:
                wage = employee.contract_id.wage or 0.0

            payslip.worked_days_line_ids.unlink()

            # Reset group summary fields
            payslip.double_pay_days = 0
            payslip.sunday_worked_days = 0
            payslip.festival_worked_days = 0
            payslip.lop_compensated_days = 0

            # -------------------------------------------------------------------
            # BUILD WORKING DAYS from calendar
            # -------------------------------------------------------------------
            all_days = []
            cur = date_from
            while cur <= date_to:
                all_days.append(cur)
                cur += timedelta(days=1)

            if group == 'group_4':
                # All 7 days are working days — no holidays
                working_days = list(all_days)
                sunday_days = set()  # Doesn't matter for group 4
                festival_dates = set()
            else:
                # Mon-Sat working; Sunday is week-off
                working_days = [d for d in all_days if not _is_sunday(d)]
                sunday_days = set(d for d in all_days if _is_sunday(d))
                festival_dates = _get_festival_dates(date_from, date_to)

            working_days_set = set(working_days)
            expected_working_days = len(working_days)
            payslip.total_working_days_in_month = expected_working_days

            # -------------------------------------------------------------------
            # ATTENDANCE: build attendance map {date: hours_worked}
            # -------------------------------------------------------------------
            attendances = Attendance.search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', datetime.combine(date_from, time.min)),
                ('check_out', '<=', datetime.combine(date_to, time.max)),
            ])

            attendance_map = {}
            for att in attendances:
                if not att.check_in or not att.check_out:
                    continue
                work_date = att.check_in.date()
                # Respect contract boundaries
                if contract.date_start and work_date < contract.date_start:
                    continue
                if contract.date_end and work_date > contract.date_end:
                    continue
                hours = (att.check_out - att.check_in).total_seconds() / 3600
                attendance_map[work_date] = max(attendance_map.get(work_date, 0), hours)

            # All days the employee actually worked (including Sundays / festival days)
            worked_any_day = set(attendance_map.keys())
            sundays_worked = sunday_days & worked_any_day
            festivals_worked = festival_dates & worked_any_day

            # -------------------------------------------------------------------
            # APPROVED LEAVES
            # -------------------------------------------------------------------
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
                    if cur in working_days_set:
                        if lv.holiday_status_id.unpaid:
                            leave_dates_unpaid.add(cur)
                        else:
                            leave_dates_paid.add(cur)
                    cur += timedelta(days=1)

            # -------------------------------------------------------------------
            # CASUAL LEAVE BUFFER (Group 1 and 2: 1 CL per month)
            # -------------------------------------------------------------------
            casual_leave_allowed = 0
            if group in ('group_1', 'group_2'):
                casual_leave_allowed = 1  # 1 Casual Leave per month

            # -------------------------------------------------------------------
            # COUNT WORKING-DAY ATTENDANCE
            # -------------------------------------------------------------------
            full_work_days = 0.0
            half_work_days = 0.0

            for d in working_days:
                if d in attendance_map:
                    hrs = attendance_map[d]
                    if hrs >= 7:
                        full_work_days += 1
                    elif hrs >= 3:
                        half_work_days += 0.5

            # Out of contract days (only applies if contract is set)
            out_days = set()
            if contract:
                out_days = set(
                    d for d in working_days
                    if (contract.date_start and d < contract.date_start)
                    or (contract.date_end and d > contract.date_end)
                )
            out_day_count = len(out_days)

            # -------------------------------------------------------------------
            # GROUP-BASED LOP / PAID CALCULATION
            # -------------------------------------------------------------------

            if group == 'group_1':
                # ---------------------------------------------------------------
                # GROUP 1: Mon-Sat | 1 CL | 12 Festival Holidays | Extra = LOP
                # Festival holidays on working week days are paid off.
                # LOP for any leave beyond the CL allowance.
                # ---------------------------------------------------------------
                # Festival days that fall on Mon-Sat are paid off (not a working day)
                # They are already excluded since we use calendar, but for safety:
                festival_on_working_days = festival_dates & working_days_set

                # Absent days on working days (not in attendance, not on leave, not festival holiday)
                auto_lop_days = set()
                cl_used = 0
                for d in working_days:
                    if d in out_days:
                        continue
                    if d in leave_dates_paid:
                        continue
                    if d in festival_on_working_days:
                        continue  # paid festival day
                    if d in attendance_map and attendance_map[d] >= 7:
                        continue
                    if d in attendance_map and attendance_map[d] >= 3:
                        continue  # half day – still working
                    # Absent: check if unpaid leave
                    if d in leave_dates_unpaid:
                        auto_lop_days.add(d)
                        continue
                    # Absent without leave → use casual leave buffer first
                    if cl_used < casual_leave_allowed:
                        cl_used += 1
                        leave_dates_paid.add(d)  # treat as CL (paid)
                    else:
                        auto_lop_days.add(d)

                paid_leave_days = len(leave_dates_paid)
                unpaid_leave_days = len(leave_dates_unpaid)
                lop_days = len(auto_lop_days)

                paid_days = full_work_days + half_work_days + paid_leave_days
                unpaid_days_total = unpaid_leave_days + lop_days

                # Sundays and festival working → no extra compensation in Group 1
                double_pay_d = 0
                lop_compensated = 0

            elif group in ('group_2', 'group_3'):
                # ---------------------------------------------------------------
                # GROUP 2 / 3:
                # - If leave on working day AND worked on Sunday → no LOP
                # - If worked all 7 days in a week → Sunday + Festival = Double Pay
                # Group 2 has 1 CL/month; Group 3 has 0 CL
                # ---------------------------------------------------------------
                festival_on_working_days = festival_dates & working_days_set

                # Identify weeks where employee worked all 7 days
                # (Mon-Sat present + Sunday present)
                # Build week map: ISO-week → {mon-sat worked set, sunday attended}
                week_map = {}
                for d in all_days:
                    iso_week = d.isocalendar()[1]
                    iso_year = d.isocalendar()[0]
                    key = (iso_year, iso_week)
                    if key not in week_map:
                        week_map[key] = {'monsat': set(), 'sunday': False}
                    if _is_sunday(d):
                        if d in worked_any_day:
                            week_map[key]['sunday'] = True
                    else:
                        if d in working_days_set and d in attendance_map and attendance_map[d] >= 7:
                            week_map[key]['monsat'].add(d)

                # A 'full 7-day week' = all Mon-Sat in that period were worked + Sunday worked
                full_week_sundays = set()
                full_week_festivals = set()
                for key, wdata in week_map.items():
                    # Count expected Mon-Sat working days in that ISO week
                    expected_ms = [
                        d for d in all_days
                        if d.isocalendar()[0] == key[0] and d.isocalendar()[1] == key[1]
                        and not _is_sunday(d)
                        and d in working_days_set
                    ]
                    if expected_ms and len(wdata['monsat']) >= len(expected_ms) and wdata['sunday']:
                        # worked all days in this week → Sunday is double pay
                        sun_day = [d for d in all_days
                                   if d.isocalendar()[0] == key[0]
                                   and d.isocalendar()[1] == key[1]
                                   and _is_sunday(d)]
                        full_week_sundays.update(sun_day)
                        full_week_festivals.update([
                            d for d in festival_on_working_days
                            if d.isocalendar()[0] == key[0]
                            and d.isocalendar()[1] == key[1]
                        ])

                double_pay_d = len(full_week_sundays) + len(full_week_festivals)

                # Sunday worked as compensation for a working-day leave
                # i.e., if employee was absent a weekday but worked that Sunday → offset LOP
                sundays_worked_non_double = sundays_worked - full_week_sundays
                # Each Sunday worked offsets 1 day of LOP/absence
                lop_offset_pool = len(sundays_worked_non_double)

                auto_lop_days = set()
                cl_used = 0
                lop_offset_used = 0
                for d in sorted(working_days):
                    if d in out_days:
                        continue
                    if d in leave_dates_paid:
                        continue
                    if d in festival_on_working_days:
                        continue  # festival = paid off
                    if d in attendance_map and attendance_map[d] >= 7:
                        continue
                    if d in attendance_map and attendance_map[d] >= 3:
                        continue
                    if d in leave_dates_unpaid:
                        # absorb with Sunday work compensation first
                        if lop_offset_used < lop_offset_pool:
                            lop_offset_used += 1
                            leave_dates_paid.add(d)
                        else:
                            auto_lop_days.add(d)
                        continue
                    # Absent without any leave
                    if cl_used < casual_leave_allowed:
                        cl_used += 1
                        leave_dates_paid.add(d)  # treat as CL (paid)
                    elif lop_offset_used < lop_offset_pool:
                        lop_offset_used += 1
                        leave_dates_paid.add(d)  # compensated by Sunday work
                    else:
                        auto_lop_days.add(d)

                lop_compensated = lop_offset_used
                paid_leave_days = len(leave_dates_paid)
                unpaid_leave_days = len(leave_dates_unpaid)
                lop_days = len(auto_lop_days)

                paid_days = full_work_days + half_work_days + paid_leave_days
                unpaid_days_total = unpaid_leave_days + lop_days

            elif group == 'group_4':
                # ---------------------------------------------------------------
                # GROUP 4: All days working. Any leave = LOP. No festival holidays.
                # ---------------------------------------------------------------
                auto_lop_days = set()
                for d in working_days:
                    if d in out_days:
                        continue
                    if d in attendance_map and attendance_map[d] >= 7:
                        continue
                    if d in attendance_map and attendance_map[d] >= 3:
                        continue
                    # Any leave or absence → LOP
                    auto_lop_days.add(d)

                paid_leave_days = 0
                lop_days = len(auto_lop_days)
                unpaid_leave_days = 0
                paid_days = full_work_days + half_work_days
                unpaid_days_total = lop_days
                double_pay_d = 0
                lop_compensated = 0

            else:
                # -------------------------------------------------------------------
                # FALLBACK: No group set → Original calendar-based logic
                # -------------------------------------------------------------------
                # CASE 1: work_entry_source == 'calendar'
                if contract.work_entry_source == 'calendar':
                    work_entries = self.env['hr.work.entry'].search([
                        ('employee_id', '=', employee.id),
                        ('date', '>=', date_from),
                        ('date', '<=', date_to),
                    ])
                    att_days = set()
                    h_days = set()
                    casual_days = set()
                    sick_days = set()
                    unpaid_we_days = set()
                    for we in work_entries:
                        d = we.date
                        if d not in working_days_set:
                            continue
                        if contract.date_start and d < contract.date_start:
                            continue
                        if contract.date_end and d > contract.date_end:
                            continue
                        code = we.work_entry_type_id.code.upper()
                        if code in ('WORK100', 'ATTENDANCE'):
                            att_days.add(d)
                        elif code in ('HALF', 'HALFDAY'):
                            h_days.add(d)
                        elif code == 'CASUAL':
                            casual_days.add(d)
                        elif code == 'SICK':
                            sick_days.add(d)
                        elif code in ('LEAVE90', 'UNPAID', 'LOP'):
                            unpaid_we_days.add(d)

                    unpaid_auto = set()
                    for d in working_days:
                        if d in out_days:
                            continue
                        if d in att_days or d in h_days:
                            continue
                        if d in casual_days or d in sick_days or d in unpaid_we_days:
                            continue
                        unpaid_auto.add(d)

                    paid_days = (len(att_days) + len(h_days) * 0.5 + len(casual_days) + len(sick_days))
                    unpaid_days_total = len(unpaid_we_days) + len(unpaid_auto)
                    double_pay_d = 0
                    lop_compensated = 0

                else:
                    # CASE 2: attendance-based (original logic)
                    festival_on_working_days = set()
                    leave_dates_paid2 = set()
                    leave_dates_unpaid2 = set()
                    for lv in leaves:
                        cur2 = max(lv.request_date_from, date_from)
                        end2 = min(lv.request_date_to, date_to)
                        while cur2 <= end2:
                            if cur2 in working_days_set:
                                if lv.holiday_status_id.unpaid:
                                    leave_dates_unpaid2.add(cur2)
                                else:
                                    leave_dates_paid2.add(cur2)
                            cur2 += timedelta(days=1)

                    paid_leave_days2 = len(leave_dates_paid2)
                    unpaid_leave_days2 = len(leave_dates_unpaid2)
                    full_work_days2 = 0.0
                    half_work_days2 = 0.0
                    for hrs in attendance_map.values():
                        if hrs >= 7:
                            full_work_days2 += 1
                        elif hrs >= 3:
                            half_work_days2 += 0.5

                    unpaid_auto2 = 0.0
                    for d in working_days:
                        if d in out_days:
                            continue
                        if d in leave_dates_paid2 or d in leave_dates_unpaid2:
                            continue
                        if d not in attendance_map:
                            unpaid_auto2 += 1
                        else:
                            hrs = attendance_map[d]
                            if 3 <= hrs < 7:
                                unpaid_auto2 += 0.5

                    paid_days = full_work_days2 + half_work_days2 + paid_leave_days2
                    unpaid_days_total = unpaid_leave_days2 + unpaid_auto2
                    double_pay_d = 0
                    lop_compensated = 0

            # -------------------------------------------------------------------
            # STORE FIELDS
            # -------------------------------------------------------------------
            payslip.paid_days = paid_days
            payslip.unpaid_days = unpaid_days_total
            payslip.double_pay_days = double_pay_d if group in ('group_2', 'group_3') else 0
            payslip.sunday_worked_days = len(sundays_worked) if group in ('group_1', 'group_2', 'group_3') else 0
            payslip.lop_compensated_days = lop_compensated if group in ('group_2', 'group_3') else 0
            payslip.festival_worked_days = len(festivals_worked) if group in ('group_1', 'group_2', 'group_3') else 0

            per_day = wage / expected_working_days if expected_working_days else 0
            payslip.paid_amount = paid_days * per_day
            payslip.unpaid_amount = unpaid_days_total * per_day

            # -------------------------------------------------------------------
            # WORKED DAYS LINES (UI)
            # -------------------------------------------------------------------
            worked_lines = []

            if full_work_days:
                worked_lines.append({
                    'name': 'Attendance',
                    'code': 'WORK100',
                    'number_of_days': full_work_days,
                    'number_of_hours': full_work_days * 8,
                    'work_entry_type_id': _get_or_create('WORK100', 'Attendance').id,
                })

            if half_work_days:
                worked_lines.append({
                    'name': 'Half Day Attendance',
                    'code': 'HALF',
                    'number_of_days': half_work_days,
                    'number_of_hours': half_work_days * 4,
                    'work_entry_type_id': _get_or_create('HALF', 'Half Day Attendance').id,
                })

            if group in ('group_1', 'group_2', 'group_3'):
                if 'paid_leave_days' in dir() or isinstance(locals().get('paid_leave_days'), (int, float)):
                    _pl = locals().get('paid_leave_days', 0) or (len(leave_dates_paid) if 'leave_dates_paid' in dir() else 0)
                    if _pl:
                        worked_lines.append({
                            'name': 'Paid Leave (CL / Festival)',
                            'code': 'CASUAL',
                            'number_of_days': _pl,
                            'number_of_hours': _pl * 8,
                            'work_entry_type_id': _get_or_create('CASUAL', 'Paid Leave').id,
                        })

            if unpaid_days_total:
                worked_lines.append({
                    'name': 'Unpaid / LOP',
                    'code': 'LEAVE90',
                    'number_of_days': unpaid_days_total,
                    'number_of_hours': unpaid_days_total * 8,
                    'work_entry_type_id': _get_or_create('LEAVE90', 'Unpaid / LOP').id,
                })

            if double_pay_d and group in ('group_2', 'group_3'):
                worked_lines.append({
                    'name': 'Double Pay Days (Sunday/Festival)',
                    'code': 'DOUBLEPAY',
                    'number_of_days': double_pay_d,
                    'number_of_hours': double_pay_d * 8,
                    'work_entry_type_id': _get_or_create('DOUBLEPAY', 'Double Pay').id,
                })

            if lop_compensated and group in ('group_2', 'group_3'):
                worked_lines.append({
                    'name': 'LOP Compensated (Sunday Work)',
                    'code': 'LOPCOMP',
                    'number_of_days': lop_compensated,
                    'number_of_hours': lop_compensated * 8,
                    'work_entry_type_id': _get_or_create('LOPCOMP', 'LOP Compensated').id,
                })

            if out_day_count:
                worked_lines.append({
                    'name': 'Out of Contract',
                    'code': 'OUT',
                    'number_of_days': out_day_count,
                    'number_of_hours': out_day_count * 8,
                    'work_entry_type_id': _get_or_create('OUT', 'Out of Contract').id,
                })

            payslip.worked_days_line_ids = [(0, 0, vals) for vals in worked_lines]

        return super(HrPayslip, self).compute_sheet()
