
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrAttendanceLine(models.Model):
    _name = "hr.attendance.line"
    _description = "Biotime Attendance Punch"

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

    biotime_transaction_id = fields.Integer(
        required=True,
        index=True
    )

    # ------------------------------------------------
    # ORM-level constraint (Odoo 19)
    # ------------------------------------------------
    @api.constrains('biotime_transaction_id')
    def _check_unique_biotime_transaction(self):
        for rec in self:
            if not rec.biotime_transaction_id:
                continue

            count = self.search_count([
                ('biotime_transaction_id', '=', rec.biotime_transaction_id),
                ('id', '!=', rec.id),
            ])

            if count:
                raise ValidationError(
                    "This Biotime transaction is already imported."
                )
