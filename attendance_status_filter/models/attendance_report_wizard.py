from odoo import models, fields
from datetime import datetime, time
import pytz


class AttendanceReportWizard(models.TransientModel):
    _name = "attendance.report.wizard"
    _description = "Attendance Report Wizard"

    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=fields.Date.context_today)

    def action_print_report(self):
        self.ensure_one()
        data = self._prepare_report_data()
        return self.env.ref(
            "attendance_status_filter.action_attendance_daily_report"
        ).report_action(self, data=data)

    def _prepare_report_data(self):
        records = []

        user_tz = pytz.timezone(self.env.user.tz or "UTC")

        # Convert Date → Datetime → UTC
        date_from_dt = user_tz.localize(
            datetime.combine(self.date_from, time.min)
        ).astimezone(pytz.UTC)

        date_to_dt = user_tz.localize(
            datetime.combine(self.date_to, time.max)
        ).astimezone(pytz.UTC)

        attendances = self.env["hr.attendance"].search([
            ("check_in", ">=", date_from_dt),
            ("check_in", "<=", date_to_dt),
        ], order="check_in asc")

        for att in attendances:
            emp = att.employee_id

            check_in_local = (
                fields.Datetime.context_timestamp(self, att.check_in)
                if att.check_in else None
            )

            records.append({
                "emp_id": emp.x_studio_emp_id or "",
                "name": emp.name,
                "job": emp.job_title or "",
                "date": check_in_local.strftime("%d-%m-%Y") if check_in_local else "",
                "check_in": check_in_local.strftime("%H:%M") if check_in_local else "",
                "check_out": (
                    fields.Datetime.context_timestamp(self, att.check_out).strftime("%H:%M")
                    if att.check_out else ""
                ),
                "status": self._compute_status(att),
            })

        return {
            "date_from": self.date_from,
            "date_to": self.date_to,
            "records": records,
        }

    def _compute_status(self, att):
        if not att.check_in:
            return "Absence (A)"

        check_in_local = fields.Datetime.context_timestamp(self, att.check_in)

        if check_in_local.time() > time(9, 30):
            return "Late (LT)"

        if not att.check_in and att.check_out:
            return "Miss In (MI)"

        return "Present (P)"