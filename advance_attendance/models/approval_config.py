from odoo import api, fields, models


class AttendanceApprovalConfig(models.Model):
    _name = 'attendance_advance.approval_config'
    _description = 'Approval mapping: request department -> approver department/employees'


    name = fields.Char(required=True)
    request_department_id = fields.Many2one('hr.department', string='Request Department', required=True)
    approver_department_id = fields.Many2one('hr.department', string='Approver Department', required=True)
    approver_employee_ids = fields.Many2many('hr.employee', string='Approvers')
    sequence = fields.Integer(default=10)


    @api.onchange('approver_department_id')
    def _onchange_approver_department(self):
        if self.approver_department_id:
            employees = self.env['hr.employee'].search([('department_id', '=', self.approver_department_id.id)])
            self.approver_employee_ids = [(6, 0, employees.ids)]

    # --- keep approvals in sync when mapping changes ---
    def _aa_sync_approvals_for_department(self, dept_id):
        if not dept_id:
            return
        # Get current top-priority config for the department
        cfg = self.env['attendance_advance.approval_config'].search([
            ('request_department_id', '=', dept_id)
        ], order='sequence asc', limit=1)
        approvers = cfg.approver_employee_ids if cfg else self.env['hr.employee']
        approvals = self.env['attendance_advance.leave_approval'].sudo().search([
            ('department_id', '=', dept_id)
        ])
        if approvals:
            approvals.sudo().write({'approver_employee_ids': [(6, 0, approvers.ids)]})
        # sync per-approver requests for all leaves in this department
        leaves = approvals.mapped('leave_id') if approvals else self.env['hr.leave'].search([('employee_id.department_id', '=', dept_id)])
        Request = self.env['attendance_advance.approval_request'].sudo()
        for leave in leaves:
            existing = Request.search([('leave_id', '=', leave.id)])
            existing_by_emp = {r.approver_employee_id.id: r for r in existing}
            for emp in approvers:
                if emp.id not in existing_by_emp:
                    Request.create({
                        'name': 'Time Off Approval',
                        'leave_id': leave.id,
                        'department_id': dept_id,
                        'approver_employee_id': emp.id,
                    })
            extra = existing.filtered(lambda r: r.approver_employee_id not in approvers)
            if extra:
                extra.sudo().unlink()

    def write(self, vals):
        res = super().write(vals)
        # Sync approvals for any impacted request departments
        for rec in self:
            self._aa_sync_approvals_for_department(rec.request_department_id.id)
        return res

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        rec._aa_sync_approvals_for_department(rec.request_department_id.id)
        return rec