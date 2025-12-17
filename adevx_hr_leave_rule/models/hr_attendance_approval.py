# models/hr_attendance_approval.py
from odoo import models, fields, api
from odoo.exceptions import UserError

class HrAttendanceApproval(models.Model):
    _name = 'hr.attendance.approval'
    _description = 'Attendance Payroll Approval'

    name = fields.Char(string='Reference', default='New', readonly=True)
    employee_id = fields.Many2one('hr.employee', required=True)
    attendance_id = fields.Many2one('hr.attendance', required=True)
    check_in = fields.Datetime(related='attendance_id.check_in', store=True)
    check_out = fields.Datetime(related='attendance_id.check_out', store=True)
    reason = fields.Text(string='Reason')
    suggested_work_type_code = fields.Selection([
        ('WORK100','Full Day'),
        ('HALF','Half Day'),
        ('UNPAID','Unpaid / LOP'),
        ('NOR_OT','Normal OT'),
        ('FRI_OT','Friday OT'),
    ], string='Work Type', required=True, default='UNPAID')
    state = fields.Selection([('draft','Draft'),('approved','Approved'),('rejected','Rejected')], default='draft')
    processed = fields.Boolean(default=False)

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        rec.name = 'APP-%s' % (rec.id or '')
        return rec

    def action_approve(self):
        for rec in self:
            if not rec.attendance_id:
                raise UserError("Attendance not found.")
            # mark attendance eligibled
            rec.attendance_id.eligibled = True
            rec.attendance_id.eligibility_note = 'Approved by HR: %s' % (self.env.user.name)
            # optionally, we could set a related work type somewhere if you want
            rec.state = 'approved'
            rec.processed = True

    def action_reject(self):
        for rec in self:
            rec.state = 'rejected'
            rec.attendance_id.eligibled = False
            rec.attendance_id.eligibility_note = 'Rejected by HR: %s' % (self.env.user.name)
