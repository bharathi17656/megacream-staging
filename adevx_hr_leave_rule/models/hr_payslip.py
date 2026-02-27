# models/hr_payslip.py
from odoo import models, fields, api
from datetime import timedelta, time, datetime
import logging

_logger = logging.getLogger(__name__)

FESTIVAL_HOLIDAY_MODEL = 'hr.festival.holiday'


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # ── summary fields shown in the "Group LOP Summary" tab ──────────────────
    unpaid_amount = fields.Float(string="Unpaid Amount", readonly=True)
    unpaid_days = fields.Float(string="Unpaid Days", readonly=True)
    paid_days = fields.Float(string="Paid Days", readonly=True)
    paid_amount = fields.Float(string="Paid Amount", readonly=True)
    total_days_in_month = fields.Float(string="Total Days in Month", readonly=True)
    total_working_days_in_month = fields.Float(string="Total Working Days in Month", readonly=True)

    # Group 2 & 3 only
    double_pay_days = fields.Float(string="Double Pay Days", readonly=True)
    sunday_worked_days = fields.Float(string="Sunday Worked Days", readonly=True)
    festival_worked_days = fields.Float(string="Festival Worked Days", readonly=True)
    lop_compensated_days = fields.Float(string="LOP Compensated (Sunday Work)", readonly=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
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
        return {h.date for h in holidays}

    def _build_attendance_map(self, employee, date_from, date_to, version):
        """Return {date: hours_worked} for the period, filtered by version dates."""
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
            # Skip dates outside the version (contract) boundaries
            if version:
                if version.contract_date_start and work_date < version.contract_date_start:
                    continue
                if version.contract_date_end and work_date > version.contract_date_end:
                    continue
            hours = (att.check_out - att.check_in).total_seconds() / 3600
            att_map[work_date] = max(att_map.get(work_date, 0), hours)
        return att_map

    # ------------------------------------------------------------------
    # Main override
    # ------------------------------------------------------------------
    def compute_sheet(self):
        """
        Pure attendance-based payroll computation (Odoo 19 compatible).

        ─ present  = attendance record ≥ 3 hrs on that day
        ─ absent   = no attendance record  →  LOP
        ─ leave applications are NOT consulted

        Group rules come from the Working Schedule (resource.calendar)
        attached to the version_id (hr.version / employee record).
        """

        for payslip in self:
            # In Odoo 19 the "contract" is hr.version, accessed via version_id
            version = payslip.version_id       # hr.version
            employee = payslip.employee_id

            if not employee:
                continue

            # Working schedule: prefer version's calendar, else employee's
            cal = (version.resource_calendar_id
                   if version and version.resource_calendar_id
                   else employee.resource_calendar_id)

            # Employee group rule lives on the Working Schedule
            group = cal.employee_group_rule if cal else False

            date_from = payslip.date_from
            date_to = payslip.date_to

            # Wage via Odoo 19's built-in helper (reads from hr.version)
            try:
                wage = payslip._get_contract_wage() or 0.0
            except Exception:
                wage = 0.0

            # Clear old worked-day lines
            payslip.worked_days_line_ids.unlink()

            # ── 1. Calendar days in period ────────────────────────────
            all_days = []
            cur = date_from
            while cur <= date_to:
                all_days.append(cur)
                cur += timedelta(days=1)

            # ── 2. Expected working days by group ─────────────────────
            def is_sunday(d):
                return d.weekday() == 6   # 0=Mon … 6=Sun

            if group == 'group_4':
                # All 7 days; no festival holidays
                working_days = list(all_days)
                sunday_days = set()
                festival_dates = set()
            else:
                # Groups 1-3: Mon-Sat
                working_days = [d for d in all_days if not is_sunday(d)]
                sunday_days = {d for d in all_days if is_sunday(d)}
                festival_dates = self._get_festival_dates(date_from, date_to)

            working_days_set = set(working_days)
            expected_working_days = len(working_days)
            payslip.total_working_days_in_month = expected_working_days

            # ── 3. Attendance map ─────────────────────────────────────
            att_map = self._build_attendance_map(employee, date_from, date_to, version)
            attended_any = set(att_map.keys())
            sundays_worked = sunday_days & attended_any
            festivals_worked = festival_dates & attended_any

            # ── 4. Out-of-contract days ───────────────────────────────
            out_days = set()
            if version:
                out_days = {
                    d for d in working_days
                    if (version.contract_date_start and d < version.contract_date_start)
                    or (version.contract_date_end and d > version.contract_date_end)
                }
            out_day_count = len(out_days)

            # ── 5. Classify each expected working day by attendance ───
            full_days = 0.0
            half_days = 0.0
            absent_days = 0
            festival_on_working = set()

            # Festival days on working days are paid off (Groups 1-3)
            if group in ('group_1', 'group_2', 'group_3'):
                festival_on_working = festival_dates & working_days_set

            for d in working_days:
                if d in out_days:
                    continue
                hrs = att_map.get(d, 0)
                if hrs >= 7:
                    full_days += 1
                elif hrs >= 3:
                    half_days += 0.5
                else:
                    # Festival paid-off days don't need attendance
                    if d in festival_on_working:
                        full_days += 1   # count as paid
                    else:
                        absent_days += 1

            festival_pd = len(festival_on_working)

            # ── 6. Group-specific adjustments ────────────────────────
            double_pay_d = 0
            lop_compensated = 0

            if group in ('group_2', 'group_3'):
                # Detect full-7-day weeks (all Mon-Sat worked + Sunday worked)
                week_map = {}
                for d in all_days:
                    iso_year, iso_week, _ = d.isocalendar()
                    key = (iso_year, iso_week)
                    if key not in week_map:
                        week_map[key] = {
                            'ms_expected': [],
                            'ms_worked': set(),
                            'sun': None,
                        }
                    if is_sunday(d):
                        week_map[key]['sun'] = d
                    elif d in working_days_set and d not in out_days:
                        week_map[key]['ms_expected'].append(d)
                        if att_map.get(d, 0) >= 7:
                            week_map[key]['ms_worked'].add(d)

                full_7day_sundays = set()
                for key, wdata in week_map.items():
                    exp = wdata['ms_expected']
                    sun = wdata['sun']
                    if (exp
                            and len(wdata['ms_worked']) >= len(exp)
                            and sun and sun in attended_any):
                        full_7day_sundays.add(sun)

                double_pay_d = len(full_7day_sundays)

                # Compensatory Sundays (worked, but NOT a full-7-day week)
                compensatory_sundays = sundays_worked - full_7day_sundays
                lop_offset = len(compensatory_sundays)
                lop_compensated = min(lop_offset, absent_days)
                absent_days = max(0, absent_days - lop_compensated)

            # ── 7. Final tallies ──────────────────────────────────────
            paid_days = full_days + half_days
            unpaid_days_total = float(absent_days)

            payslip.paid_days = paid_days
            payslip.unpaid_days = unpaid_days_total
            payslip.double_pay_days = float(double_pay_d)
            payslip.sunday_worked_days = float(len(sundays_worked))
            payslip.festival_worked_days = float(len(festivals_worked))
            payslip.lop_compensated_days = float(lop_compensated)

            per_day = wage / expected_working_days if expected_working_days else 0
            payslip.paid_amount = paid_days * per_day
            payslip.unpaid_amount = unpaid_days_total * per_day

            # ── 8. Worked-days lines (UI) ─────────────────────────────
            def wet(code, name):
                return self._get_or_create_work_entry_type(code, name).id

            lines = []

            if full_days:
                lines.append({
                    'name': 'Present (Full Day)',
                    'code': 'WORK100',
                    'number_of_days': full_days,
                    'number_of_hours': full_days * 8,
                    'work_entry_type_id': wet('WORK100', 'Attendance'),
                })
            if half_days:
                lines.append({
                    'name': 'Present (Half Day)',
                    'code': 'HALF',
                    'number_of_days': half_days,
                    'number_of_hours': half_days * 4,
                    'work_entry_type_id': wet('HALF', 'Half Day Attendance'),
                })
            if festival_pd and group in ('group_1', 'group_2', 'group_3'):
                lines.append({
                    'name': 'Festival Holiday (Paid Off)',
                    'code': 'FESTIVAL',
                    'number_of_days': festival_pd,
                    'number_of_hours': festival_pd * 8,
                    'work_entry_type_id': wet('FESTIVAL', 'Festival Holiday'),
                })
            if unpaid_days_total:
                lines.append({
                    'name': 'Absent / LOP',
                    'code': 'LEAVE90',
                    'number_of_days': unpaid_days_total,
                    'number_of_hours': unpaid_days_total * 8,
                    'work_entry_type_id': wet('LEAVE90', 'Unpaid / LOP'),
                })
            if lop_compensated and group in ('group_2', 'group_3'):
                lines.append({
                    'name': 'LOP Compensated (Sunday Work)',
                    'code': 'LOPCOMP',
                    'number_of_days': lop_compensated,
                    'number_of_hours': lop_compensated * 8,
                    'work_entry_type_id': wet('LOPCOMP', 'LOP Compensated'),
                })
            if double_pay_d and group in ('group_2', 'group_3'):
                lines.append({
                    'name': 'Double Pay (7-Day Week)',
                    'code': 'DOUBLEPAY',
                    'number_of_days': double_pay_d,
                    'number_of_hours': double_pay_d * 8,
                    'work_entry_type_id': wet('DOUBLEPAY', 'Double Pay'),
                })
            if out_day_count:
                lines.append({
                    'name': 'Out of Contract',
                    'code': 'OUT',
                    'number_of_days': out_day_count,
                    'number_of_hours': out_day_count * 8,
                    'work_entry_type_id': wet('OUT', 'Out of Contract'),
                })

            payslip.worked_days_line_ids = [(0, 0, v) for v in lines]

        # Call Odoo's original compute_sheet to process salary rules
        return super().compute_sheet()
