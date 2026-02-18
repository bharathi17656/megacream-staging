
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


    def _recompute_attendance_from_lines(self, employee_id, date):
        HrAttendance = self.env['hr.attendance']
        HrAttendanceLine = self.env['hr.attendance.line']
    
        start_dt = datetime.combine(date, datetime.min.time())
        end_dt = datetime.combine(date, datetime.max.time())
    
        lines = HrAttendanceLine.search([
            ('employee_id', '=', employee_id),
            ('punch_time', '>=', start_dt),
            ('punch_time', '<=', end_dt),
        ], order="punch_time asc")
    
        if not lines:
            return
    
        check_in = lines[0].punch_time
        check_out = lines[-1].punch_time if len(lines) > 1 else False
    
        attendance = HrAttendance.search([
            ('employee_id', '=', employee_id),
            ('check_in', '>=', start_dt),
            ('check_in', '<=', end_dt),
        ], limit=1)
    
        vals = {
            'employee_id': employee_id,
            'check_in': check_in,
            'check_out': check_out if check_out and check_out > check_in else False,
            'x_studio_no_checkout': False if check_out else True,
        }
    
        if attendance:
            attendance.write(vals)
        else:
            attendance = HrAttendance.create(vals)
    
        # link lines
        lines.write({'attendance_id': attendance.id})
    
    @api.model
    def cron_recompute_all_attendance(self):
        HrAttendanceLine = self.env['hr.attendance.line']
    
        lines = HrAttendanceLine.search([])
    
        grouped = {}
    
        for line in lines:
            date = line.punch_time.date()
            grouped.setdefault(
                (line.employee_id.id, date),
                []
            ).append(line)
    
        for (employee_id, date), _ in grouped.items():
            self._recompute_attendance_from_lines(employee_id, date)

    
    

