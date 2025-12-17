from odoo import models, fields, api
from datetime import datetime

class AttendanceActivityWizard(models.TransientModel):
    _name = 'attendance.activity.wizard'
    _description = 'Attendance Activity Wizard'

    activity = fields.Char(string="Activity", required=True)
    attendance_id = fields.Many2one('hr.attendance', string="Attendance")

    def action_submit_activity(self):
        """Save activity and checkout."""
        self.ensure_one()
        if self.attendance_id:
            self.attendance_id.write({
                'check_out': datetime.now(),
                'activity': self.activity
            })
