from odoo import models, fields


class ReportMonthlyAttendance(models.AbstractModel):
    _name = 'report.attendance_status_filter.monthly_attendance_template'
    _description = 'Monthly Attendance Report'

    def _get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'monthly.attendance.wizard',
            'data': data,
            'generated_on': fields.Datetime.now(),
        }