# models/hr_payslip.py
from odoo import models, fields, api
from datetime import timedelta, time, datetime
import logging

_logger = logging.getLogger(__name__)

FESTIVAL_HOLIDAY_MODEL = 'resource.calendar.leaves'


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

    # Calendar summary
    total_saturdays_in_month = fields.Float(string="Total Saturdays in Month", readonly=True)
    total_sundays_in_month = fields.Float(string="Total Sundays in Month", readonly=True)

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
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
        ])
        return {h.date_from.date() for h in holidays if h.date_from}

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

        Key formula:
          per_day  = wage / total_calendar_days_in_month
          present  = attendance record ≥ 3 hrs → full (≥7 hrs) or half (≥3 hrs)
          absent   = no attendance on a Mon–Sat working day → LOP at per_day rate

        Leave applications are NOT consulted.
        Group rules come from the Working Schedule (resource.calendar.employee_group_rule).
        """

        for payslip in self:
            version = payslip.version_id       # hr.version (Odoo 19 contract equivalent)
            employee = payslip.employee_id

            if not employee:
                continue

            # Working schedule: prefer version's calendar, else employee's
            cal = (version.resource_calendar_id
                   if version and version.resource_calendar_id
                   else employee.resource_calendar_id)

            group = cal.employee_group_rule if cal else False
            date_from = payslip.date_from
            date_to = payslip.date_to

            # Wage via Odoo 19 built-in helper
            try:
                wage = payslip._get_contract_wage() or 0.0
            except Exception:
                wage = 0.0

            payslip.worked_days_line_ids.unlink()

            # ── 1. Build all calendar days in the payslip period ─────
            all_days = []
            cur = date_from
            while cur <= date_to:
                all_days.append(cur)
                cur += timedelta(days=1)

            total_calendar_days = len(all_days)
            payslip.total_days_in_month = total_calendar_days

            # KEY FIX: per-day rate = wage / total calendar days
            per_day = wage / total_calendar_days if total_calendar_days else 0

            # ── 2. Expected working days by group ─────────────────────
            def is_sunday(d):
                return d.weekday() == 6    # 0=Mon … 6=Sun

            if group == 'group_4':
                # All 7 days are working; no festival holidays
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

            # ── 3. Attendance map {date: hours_worked} ────────────────
            att_map = self._build_attendance_map(employee, date_from, date_to, version)
            attended_any = set(att_map.keys())
            sundays_worked = sunday_days & attended_any

            # ── 4. Out-of-contract days ───────────────────────────────
            out_days = set()
            if version:
                out_days = {
                    d for d in working_days
                    if (version.contract_date_start and d < version.contract_date_start)
                    or (version.contract_date_end and d > version.contract_date_end)
                }
            out_day_count = len(out_days)

            # ── 5. Festival paid-off days (Groups 1-3) ────────────────
            festival_on_working = set()
            if group in ('group_1', 'group_2', 'group_3'):
                festival_on_working = festival_dates & working_days_set
            festivals_worked = festival_dates & attended_any

            # ── 6. Classify each expected working day by attendance ───
            full_days = 0.0
            half_days = 0.0
            absent_days = 0
            absent_day_list = []   # tracks dates of absent Mon–Sat days

            for d in working_days:
                if d in out_days:
                    continue
                if d in festival_on_working:
                    # Festival day on working day = paid off, no attendance needed
                    full_days += 1
                    continue
                hrs = att_map.get(d, 0)
                if hrs >= 7:
                    full_days += 1
                elif hrs >= 3:
                    half_days += 0.5
                else:
                    absent_days += 1
                    absent_day_list.append(d)

            festival_pd = len(festival_on_working)

            # Festival Present: festivals on working days where employee
            # actually worked (Groups 2/3 only). These are removed from
            # Present and can offset LOP like Sundays.
            festival_present_count = 0
            if group in ('group_2', 'group_3'):
                festival_present_set = festival_on_working & attended_any
                festival_present_count = len(festival_present_set)
                full_days -= festival_present_count   # will show separately

            # ── 7. Group-specific: Sunday compensation & Paid Leave ───

            # Capture ORIGINAL absent count here (before paid leave or LOP comp)
            # so the Present line shows: wage - (absent_before_comp × per_day)
            absent_before_comp = absent_days

            # ── Group 2: 1-day paid leave allowance per month ──────────
            group2_paid_leave_dates = set()
            paid_leave_credit = 0
            if group == 'group_2':
                paid_leave_quota = 1
                pl_taken = absent_day_list[:paid_leave_quota]
                group2_paid_leave_dates = set(pl_taken)
                paid_leave_credit = len(group2_paid_leave_dates)
                absent_days = max(0, absent_days - paid_leave_credit)

            # ── Group 1: 1 casual leave per month ──────────────────────
            casual_leave_credit = 0
            if group == 'group_1':
                casual_leave_quota = 1
                cl_taken = absent_day_list[:casual_leave_quota]
                casual_leave_credit = len(cl_taken)
                absent_days = max(0, absent_days - casual_leave_credit)

            if group in ('group_2', 'group_3'):
                # ── Combined compensation pool: Sundays + Festival Present ──
                total_sundays_worked = len(sundays_worked)
                comp_pool = total_sundays_worked + festival_present_count
                total_compensated = min(absent_days, comp_pool)
                remaining_lop = max(0, absent_days - comp_pool)

                # Allocate: Sundays first, then Festival Present
                sunday_compensated = min(total_sundays_worked, total_compensated)
                festival_compensated = total_compensated - sunday_compensated
                extra_sunday = max(0, total_sundays_worked - sunday_compensated)
                festival_present_extra = max(0, festival_present_count - festival_compensated)

                absent_days = remaining_lop
            else:
                sunday_compensated = 0
                extra_sunday = 0
                festival_compensated = 0
                festival_present_extra = 0

            # ── 8. Final tallies ──────────────────────────────────────
            # paid_days = attendance + festival paid-offs + any leave credits
            paid_days = full_days + half_days + paid_leave_credit + casual_leave_credit
            unpaid_days_total = float(absent_days)

            payslip.paid_days = paid_days
            payslip.unpaid_days = unpaid_days_total
            payslip.double_pay_days = float(extra_sunday)
            payslip.sunday_worked_days = float(len(sundays_worked))
            payslip.festival_worked_days = float(len(festivals_worked))
            payslip.lop_compensated_days = float(sunday_compensated)
            payslip.paid_amount = paid_days * per_day
            payslip.unpaid_amount = unpaid_days_total * per_day
            payslip.total_saturdays_in_month = float(sum(1 for d in all_days if d.weekday() == 5))
            payslip.total_sundays_in_month = float(len(sunday_days))

            # ── 9. Build worked_days lines with explicit amounts ──────
            #
            # FORMULA:
            #   per_day = wage / total_calendar_days   (e.g. 15000/28 for Feb)
            #
            #   Present (Full Day) amount = wage - (absent_before_comp * per_day)
            #     → shows full salary minus the raw LOP deduction
            #     → LOP Compensated & Double Pay then appear as clean additions
            #
            #   Example (Feb, ₹15,000, 23 present, 1 absent, 4 Sundays worked):
            #     per_day            = 15000/28 = ₹535.71
            #     Present (Full Day) = 15000 - 535.71 = ₹14,464.29
            #     LOP Compensated    = 1 × 535.71    = ₹535.71
            #     Double Pay         = 3 × 535.71    = ₹1,607.14
            #     Net                               = ₹16,607.14

            def wet(code, name):
                return self._get_or_create_work_entry_type(code, name).id

            lines = []

            if full_days:
                # ── Present line amount (ALL groups) ──────────────────────────
                # amount = (total_calendar_days - absent_before_comp) × per_day
                #        = wage - absent_before_comp × per_day
                # Days column shows actual attendance (full_days)
                present_amount = round(wage - absent_before_comp * per_day, 2)

                lines.append({
                    'name': 'Present (Full Day)',
                    'code': 'WORK100',
                    'number_of_days': full_days,
                    'number_of_hours': full_days * 8,
                    'amount': present_amount,
                    'work_entry_type_id': wet('WORK100', 'Attendance'),
                })

            if half_days:
                lines.append({
                    'name': 'Present (Half Day)',
                    'code': 'HALF',
                    'number_of_days': half_days,
                    'number_of_hours': half_days * 4,
                    'amount': round(half_days * per_day, 2),
                    'work_entry_type_id': wet('HALF', 'Half Day Attendance'),
                })

            if festival_pd and group in ('group_1', 'group_2', 'group_3'):
                lines.append({
                    'name': 'Festival Holiday (Paid Off)',
                    'code': 'FESTIVAL',
                    'number_of_days': festival_pd,
                    'number_of_hours': festival_pd * 8,
                    'amount': round(festival_pd * per_day, 2),
                    'work_entry_type_id': wet('FESTIVAL', 'Festival Holiday'),
                })

            if unpaid_days_total:
                lines.append({
                    'name': 'Absent / LOP',
                    'code': 'LEAVE90',
                    'number_of_days': unpaid_days_total,
                    'number_of_hours': unpaid_days_total * 8,
                    # 'amount': round(-unpaid_days_total * per_day, 2),   # negative deduction
                    'amount':0.0,
                    'work_entry_type_id': wet('LEAVE90', 'Unpaid / LOP'),
                })

            # Group 2 paid leave: adds back the deduction shown in Present line
            if paid_leave_credit and group == 'group_2':
                lines.append({
                    'name': 'Paid Leave (Group 2)',
                    'code': 'PAIDLEAVE',
                    'number_of_days': float(paid_leave_credit),
                    'number_of_hours': paid_leave_credit * 8,
                    'amount': round(paid_leave_credit * per_day, 2),
                    'work_entry_type_id': wet('PAIDLEAVE', 'Paid Leave'),
                })

            # Group 1 casual leave: 1st absent day is paid
            if casual_leave_credit and group == 'group_1':
                lines.append({
                    'name': 'Casual Leave (Group 1)',
                    'code': 'CASUALLEAVE',
                    'number_of_days': float(casual_leave_credit),
                    'number_of_hours': casual_leave_credit * 8,
                    'amount': round(casual_leave_credit * per_day, 2),
                    'work_entry_type_id': wet('CASUALLEAVE', 'Casual Leave'),
                })

            # Sunday Compensated: Sundays used to offset LOP (Groups 2/3)
            if sunday_compensated and group in ('group_2', 'group_3'):
                lines.append({
                    'name': 'Sunday Compensated',
                    'code': 'LOPCOMP',
                    'number_of_days': float(sunday_compensated),
                    'number_of_hours': sunday_compensated * 8,
                    'amount': round(sunday_compensated * per_day, 2),
                    'work_entry_type_id': wet('LOPCOMP', 'Sunday Compensated'),
                })

            # Festival Present: employee worked on a festival holiday (Groups 2/3)
            # Shows all festival present days; those used for LOP comp + extras
            if festival_present_count and group in ('group_2', 'group_3'):
                lines.append({
                    'name': 'Festival Present',
                    'code': 'FESTPRESENT',
                    'number_of_days': float(festival_present_count),
                    'number_of_hours': festival_present_count * 8,
                    'amount': round(festival_present_count * per_day, 2),
                    'work_entry_type_id': wet('FESTPRESENT', 'Festival Present'),
                })

            # Extra Work Sunday: surplus Sundays beyond LOP offset (Groups 2/3)
            if extra_sunday and group in ('group_2', 'group_3'):
                lines.append({
                    'name': 'Extra Work Sunday',
                    'code': 'DOUBLEPAY',
                    'number_of_days': float(extra_sunday),
                    'number_of_hours': extra_sunday * 8,
                    'amount': round(extra_sunday * per_day, 2),
                    'work_entry_type_id': wet('DOUBLEPAY', 'Extra Work Sunday'),
                })

            if out_day_count:
                lines.append({
                    'name': 'Out of Contract',
                    'code': 'OUT',
                    'number_of_days': out_day_count,
                    'number_of_hours': out_day_count * 8,
                    'amount': 0.0,
                    'work_entry_type_id': wet('OUT', 'Out of Contract'),
                })

            payslip.worked_days_line_ids = [(0, 0, v) for v in lines]

        return super().compute_sheet()
