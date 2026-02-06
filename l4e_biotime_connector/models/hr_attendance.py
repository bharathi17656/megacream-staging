from odoo import models, fields

class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    attendance_line_ids = fields.One2many(
        "hr.attendance.line",
        "attendance_id",
        string="Biometric Punches"
    )
