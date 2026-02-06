from odoo import models, fields

class HrAttendanceLine(models.Model):
    _name = "hr.attendance.line"
    _description = "Biotime Attendance Punch"
    _order = "punch_time"

    attendance_id = fields.Many2one(
        "hr.attendance",
        ondelete="cascade"
    )
    employee_id = fields.Many2one(
        "hr.employee",
        required=True,
        index=True
    )

    punch_time = fields.Datetime(required=True)
    punch_state = fields.Selection([
        ('0', 'IN'),
        ('1', 'OUT'),
    ])
    terminal_sn = fields.Char()
    terminal_alias = fields.Char()

    biotime_transaction_id = fields.BigInteger(index=True)

    _sql_constraints = [
        (
            "uniq_biotime_tx",
            "unique(biotime_transaction_id)",
            "Duplicate Biotime transaction"
        )
    ]
