from odoo import api, fields, models, _


class AttendanceAdvanceLeaveApproval(models.Model):
    _name = 'attendance_advance.leave_approval'
    _description = 'Time Off Approval (Advance Attendance)'
    _order = 'id desc'

    name = fields.Char(string='Title', required=True, default=lambda self: _('Time Off Approval'))
    leave_id = fields.Many2one('hr.leave', string='Time Off', required=True, ondelete='cascade', index=True)
    department_id = fields.Many2one('hr.department', string='Request Department', readonly=True)

    approver_employee_ids = fields.Many2many('hr.employee', string='Approvers')
    approver_user_ids = fields.Many2many(
        'res.users', string='Approver Users',
        compute='_compute_approver_users', store=True, compute_sudo=True,
        help='Computed from approver employees for access rules')

    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
    ], string='Status', compute='_compute_status', store=False)

    _sql_constraints = [
        ('leave_unique', 'unique(leave_id)', 'Only one approval record per Time Off is allowed.'),
    ]

    @api.depends('leave_id.state')
    def _compute_status(self):
        for rec in self:
            state = rec.leave_id.state
            if state in ('validate', 'validate1'):
                rec.status = 'approved'
            elif state == 'refuse':
                rec.status = 'refused'
            else:
                rec.status = 'pending'

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

    @api.depends('approver_employee_ids')
    def _compute_approver_users(self):
        for rec in self:
            users = rec.approver_employee_ids.mapped('user_id')
            rec.approver_user_ids = [(6, 0, users.ids)]
