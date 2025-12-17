from odoo import api, fields, models, _


class AttendanceAdvanceApprovalRequest(models.Model):
    _name = 'attendance_advance.approval_request'
    _description = 'Time Off Approval Request (per approver)'
    _order = 'id desc'

    name = fields.Char(string='Title', required=True, default=lambda self: _('Time Off Approval'))
    leave_id = fields.Many2one('hr.leave', string='Time Off', required=True, ondelete='cascade', index=True)
    department_id = fields.Many2one('hr.department', string='Request Department', readonly=True)

    approver_employee_id = fields.Many2one('hr.employee', string='Approver Employee', required=True)
    approver_user_id = fields.Many2one('res.users', string='Approver User', related='approver_employee_id.user_id', store=True, readonly=True)

    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
    ], string='Status', default='pending', tracking=True)

    _sql_constraints = [
        ('leave_approver_unique', 'unique(leave_id, approver_employee_id)', 'Only one approval request per approver per Time Off is allowed.'),
    ]

    def action_open_leave(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Time Off Request'),
            'res_model': 'hr.leave',
            'res_id': self.leave_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        # Optional: notify approver via activity
        # if rec.approver_user_id:
        #     rec.activity_schedule(
        #         'mail.mail_activity_data_todo',
        #         user_id=rec.approver_user_id.id,
        #         summary=_('Time Off Approval Request'),
        #         note=_('Please review and approve the Time Off request'),
        #     )
        return rec
