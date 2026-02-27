from odoo import models, fields
from datetime import date, datetime, time
import calendar
import pytz


class MonthlyAttendanceWizard(models.TransientModel):
    _name = "monthly.attendance.wizard"
    _description = "Monthly Attendance Wizard"

    month = fields.Selection(
        [(str(i), calendar.month_name[i]) for i in range(1, 13)],
        string="Month",
        required=True,
        default=lambda self: str(date.today().month),
    )
    year = fields.Selection(
        selection=lambda self: self._get_year_selection(),
        string="Year",
        required=True,
        default=lambda self: str(date.today().year),
    )

    def _get_year_selection(self):
        start_year = 2026
        current_year = date.today().year

        years = []
        for y in range(start_year, current_year + 6):
            years.append((str(y), str(y)))

        return years

    def action_print_monthly(self):
        self.ensure_one()
        data = self._prepare_report_data()
        return self.env.ref(
            "attendance_status_filter.action_attendance_monthly_report"
        ).report_action(self, data=data)

    def _prepare_report_data(self):
        month = int(self.month)
        year = int(self.year)  # ✅ FIXED
        days_in_month = calendar.monthrange(year, month)[1]

        days = []
        for d in range(1, days_in_month + 1):
            dt = date(year, month, d)
            days.append({
                "day": dt.strftime("%a"),
                "date": d,
            })

        employees = self.env["hr.employee"].search([
            ("active", "=", True),
            ("user_id", "!=", self.env.ref("base.user_admin").id)
        ], order="name")

        tz = pytz.timezone(self.env.user.tz or "UTC")

        start_month = tz.localize(datetime(year, month, 1)).astimezone(pytz.UTC)
        end_month = tz.localize(
            datetime(year, month, days_in_month, 23, 59, 59)
        ).astimezone(pytz.UTC)

        all_attendances = self.env["hr.attendance"].search([
            ("check_in", ">=", start_month),
            ("check_in", "<=", end_month),
        ])

        attendance_map = {}
        for att in all_attendances:
            emp_id = att.employee_id.id
            check_date = fields.Datetime.context_timestamp(
                self, att.check_in
            ).date()

            attendance_map.setdefault(emp_id, {})
            if check_date not in attendance_map[emp_id]:
                attendance_map[emp_id][check_date] = att

        records = []
        sl_no = 1

        for emp in employees:
            row = []
            for d in range(1, days_in_month + 1):
                dt = date(year, month, d)
                att = attendance_map.get(emp.id, {}).get(dt)
                row.append(self._status(att))

            records.append({
                "sl_no": sl_no,
                "name": emp.name,
                "attendance": row,
            })
            sl_no += 1

        return {
            "date_from": date(year, month, 1).strftime("%B %d %Y"),
            "date_to": date(year, month, days_in_month).strftime("%B %d %Y"),
            "month_name": calendar.month_name[month],
            "year": year,
            "month_year": f"{calendar.month_name[month]} {year}",
            "days": days,
            "records": records,
        }

    def _status(self, att):
        if not att:
            return "A"

        if not att.check_in:
            return "MI" if att.check_out else "A"

        check_in = fields.Datetime.context_timestamp(self, att.check_in)

        if check_in.time() > time(9, 30):
            return "LT"

        return "P"

    # def _status(self, att):
    #     if not att:
    #         return "A"
    #
    #     check_in = fields.Datetime.context_timestamp(self, att.check_in)
    #
    #     if check_in.time() > time(9, 30):
    #         return "LT"
    #
    #     return "P"