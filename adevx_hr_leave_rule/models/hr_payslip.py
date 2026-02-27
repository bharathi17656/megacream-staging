# models/hr_payslip.py
from odoo import models, fields, api
from datetime import timedelta, time, datetime
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

    # Group-Based summary fields (Group 2 & 3 only)
    double_pay_days = fields.Float(string="Double Pay Days", readonly=True)
    sunday_worked_days = fields.Float(string="Sunday Worked Days", readonly=True)
    festival_worked_days = fields.Float(string="Festival Worked Days", readonly=True)
    lop_compensated_days = fields.Float(string="LOP Compensated (Sunday Work)", readonly=True)

    def compute_sheet(self):
        """
        Pure attendance-based payroll computation:
          - Present  = attendance record found for that day (>= 3 hrs → full/half)
          - Absent   = no attendance record found → LOP

        Leave applications are NOT used for presence/absence decisions.
        Group rules on the Working Schedule control:
          - Which days are 'expected working days'
          - Festival holiday treatment
          - Sunday-work LOP compensation (Group 2 & 3)
          - Double-pay for 7-day weeks (Group 2 & 3)
        """
        WorkEntryType = self.env['hr.work.entry.type']

        def _get_or_create(code, name):
            rec = WorkEntryType.search([('code', '=', code)], limit=1)
            if not rec:
                rec = WorkEntryType.create({'name': name, 'code': code})
            return rec

        def _is_sunday(d):
            return d.weekday() == 6  # 0=Mon … 6=Sun

        def _get_festival_dates(date_from, date_to):
            holidays = self.env[FESTIVAL_HOLIDAY_MODEL].search([
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ])
            return {h.date for h in holidays}

        def _build_attendance_map(employee, date_from, date_to, contract):
            """Return {date: hours_worked} for the payslip period."""
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
                # Skip outside contract boundaries
                if contract:
                    if contract.date_start and work_date < contract.date_start:
                        continue
                    if contract.date_end and work_date > contract.date_end:
                        continue
                hours = (att.check_out - att.check_in).total_seconds() / 3600
                att_map[work_date] = max(att_map.get(work_date, 0), hours)
            return att_map

        for payslip in self:
            employee = payslip.employee_id
            contract = payslip.contract_id  # may be empty in some Odoo 19 flows
            if not employee:
                continue

            # Working schedule from employee (Odoo 19 style)
            cal = employee.resource_calendar_id
            group = cal.employee_group_rule if cal else False
            date_from = payslip.date_from
            date_to = payslip.date_to

            # Wage
            wage = 0.0
            if contract and hasattr(contract, 'wage'):
                wage = contract.wage or 0.0
            elif hasattr(employee, 'contract_id') and employee.contract_id:
                wage = employee.contract_id.wage or 0.0

            payslip.worked_days_line_ids.unlink()

            # ----------------------------------------------------------------
            # 1. BUILD ALL CALENDAR DAYS IN PERIOD
            # ----------------------------------------------------------------
            all_days = []
            cur = date_from
            while cur <= date_to:
                all_days.append(cur)
                cur += timedelta(days=1)

            # ----------------------------------------------------------------
            # 2. EXPECTED WORKING DAYS (by group)
            # ----------------------------------------------------------------
            if group == 'group_4':
                # All 7 days are working days; no festival holidays
                working_days = list(all_days)
                sunday_days = set()
                festival_dates = set()
            else:
                # Groups 1, 2, 3: Mon-Sat working; Sunday is week-off
                working_days = [d for d in all_days if not _is_sunday(d)]
                sunday_days = {d for d in all_days if _is_sunday(d)}
                festival_dates = _get_festival_dates(date_from, date_to)

            working_days_set = set(working_days)
            expected_working_days = len(working_days)
            payslip.total_working_days_in_month = expected_working_days

            # ----------------------------------------------------------------
            # 3. ATTENDANCE MAP  {date: hours}
            # ----------------------------------------------------------------
            att_map = _build_attendance_map(employee, date_from, date_to, contract)

            # Days employee actually attended (on any day incl. Sundays)
            attended_any = set(att_map.keys())
            sundays_worked = sunday_days & attended_any
            festivals_worked = festival_dates & attended_any

            # ----------------------------------------------------------------
            # 4. OUT-OF-CONTRACT DAYS
            # ----------------------------------------------------------------
            out_days = set()
            if contract:
                out_days = {
                    d for d in working_days
                    if (contract.date_start and d < contract.date_start)
                    or (contract.date_end and d > contract.date_end)
                }
            out_day_count = len(out_days)

            # ----------------------------------------------------------------
            # 5. CLASSIFY EACH EXPECTED WORKING DAY (purely by attendance)
            # ----------------------------------------------------------------
            full_days = 0.0    # >= 7 hrs
            half_days = 0.0    # >= 3 hrs and < 7 hrs
            absent_days = 0    # no attendance at all on that working day

            absent_day_list = []  # used for Sunday-compensation offset

            for d in working_days:
                if d in out_days:
                    continue
                hrs = att_map.get(d, 0)
                if hrs >= 7:
                    full_days += 1
                elif hrs >= 3:
                    half_days += 0.5
                else:
                    absent_days += 1
                    absent_day_list.append(d)

            # ----------------------------------------------------------------
            # 6. GROUP-SPECIFIC ADJUSTMENTS
            # ----------------------------------------------------------------
            double_pay_d = 0
            lop_compensated = 0
            festival_pd = 0  # festival days treated as paid (not LOP)

            if group in ('group_1', 'group_2', 'group_3'):
                # Festival days on expected working days → treated as PAID OFF
                festival_on_working = festival_dates & working_days_set
                festival_pd = len(festival_on_working)
                # Reduce absent count for those paid festival days (employee needn't attend)
                festival_absent_offset = len(festival_on_working - attended_any)
                absent_days = max(0, absent_days - festival_absent_offset)

            if group in ('group_2', 'group_3'):
                # Sunday-work → offsets 1 absent day each
                # (Sundays NOT in a full-7-day week are compensatory)

                # Full-7-day week detection: all Mon-Sat worked + Sunday worked
                week_map = {}
                for d in all_days:
                    iso_year, iso_week, _ = d.isocalendar()
                    key = (iso_year, iso_week)
                    week_map.setdefault(key, {'ms_expected': [], 'ms_worked': set(), 'sun': None})
                    if _is_sunday(d):
                        week_map[key]['sun'] = d
                    elif d in working_days_set:
                        week_map[key]['ms_expected'].append(d)
                        if att_map.get(d, 0) >= 7:
                            week_map[key]['ms_worked'].add(d)

                full_7day_sundays = set()
                for key, wdata in week_map.items():
                    exp = wdata['ms_expected']
                    sun = wdata['sun']
                    if exp and len(wdata['ms_worked']) >= len(exp) and sun and sun in attended_any:
                        full_7day_sundays.add(sun)
                        # Festival days in this week also get double pay
                        for fd in festival_on_working if 'festival_on_working' in dir() else []:
                            iso = fd.isocalendar()
                            if (iso[0], iso[1]) == key:
                                full_7day_sundays.add(fd)

                double_pay_d = len(full_7day_sundays)

                # Compensatory Sundays (worked, but not part of a full-7-day week)
                compensatory_sundays = sundays_worked - full_7day_sundays
                lop_offset = len(compensatory_sundays)

                # Apply Sunday compensation: reduce absent_days
                lop_compensated = min(lop_offset, absent_days)
                absent_days = max(0, absent_days - lop_compensated)

            # ----------------------------------------------------------------
            # 7. FINAL TALLIES
            # ----------------------------------------------------------------
            paid_days = full_days + half_days + festival_pd
            unpaid_days_total = float(absent_days)

            payslip.paid_days = paid_days
            payslip.unpaid_days = unpaid_days_total
            payslip.double_pay_days = double_pay_d
            payslip.sunday_worked_days = float(len(sundays_worked))
            payslip.festival_worked_days = float(len(festivals_worked))
            payslip.lop_compensated_days = float(lop_compensated)

            per_day = wage / expected_working_days if expected_working_days else 0
            payslip.paid_amount = paid_days * per_day
            payslip.unpaid_amount = unpaid_days_total * per_day

            # ----------------------------------------------------------------
            # 8. WORKED DAYS LINES (UI)
            # ----------------------------------------------------------------
            worked_lines = []

            if full_days:
                worked_lines.append({
                    'name': 'Present (Full Day)',
                    'code': 'WORK100',
                    'number_of_days': full_days,
                    'number_of_hours': full_days * 8,
                    'work_entry_type_id': _get_or_create('WORK100', 'Attendance').id,
                })

            if half_days:
                worked_lines.append({
                    'name': 'Present (Half Day)',
                    'code': 'HALF',
                    'number_of_days': half_days,
                    'number_of_hours': half_days * 4,
                    'work_entry_type_id': _get_or_create('HALF', 'Half Day Attendance').id,
                })

            if festival_pd and group in ('group_1', 'group_2', 'group_3'):
                worked_lines.append({
                    'name': 'Festival Holiday (Paid Off)',
                    'code': 'FESTIVAL',
                    'number_of_days': festival_pd,
                    'number_of_hours': festival_pd * 8,
                    'work_entry_type_id': _get_or_create('FESTIVAL', 'Festival Holiday').id,
                })

            if unpaid_days_total:
                worked_lines.append({
                    'name': 'Absent / LOP',
                    'code': 'LEAVE90',
                    'number_of_days': unpaid_days_total,
                    'number_of_hours': unpaid_days_total * 8,
                    'work_entry_type_id': _get_or_create('LEAVE90', 'Unpaid / LOP').id,
                })

            if lop_compensated and group in ('group_2', 'group_3'):
                worked_lines.append({
                    'name': 'LOP Compensated (Sunday Work)',
                    'code': 'LOPCOMP',
                    'number_of_days': lop_compensated,
                    'number_of_hours': lop_compensated * 8,
                    'work_entry_type_id': _get_or_create('LOPCOMP', 'LOP Compensated').id,
                })

            if double_pay_d and group in ('group_2', 'group_3'):
                worked_lines.append({
                    'name': 'Double Pay (7-Day Week - Sunday/Festival)',
                    'code': 'DOUBLEPAY',
                    'number_of_days': double_pay_d,
                    'number_of_hours': double_pay_d * 8,
                    'work_entry_type_id': _get_or_create('DOUBLEPAY', 'Double Pay').id,
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
