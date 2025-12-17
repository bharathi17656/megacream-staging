import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    # Show related approval containers on the leave form
    approval_advance_ids = fields.One2many(
        'attendance_advance.leave_approval', 'leave_id',
        string='Advanced Approvals', readonly=True)
    approval_request_ids = fields.One2many(
        'attendance_advance.approval_request', 'leave_id',
        string='Per-Approver Requests', readonly=True)

    # Computed approver users (for access rules and quick checks)
    aa_approver_user_ids = fields.Many2many(
        'res.users', string='Advanced Approvers (Users)',
        compute='_compute_aa_approver_users', store=True, compute_sudo=True)

    @api.depends('approval_advance_ids', 'approval_advance_ids.approver_user_ids')
    def _compute_aa_approver_users(self):
        for leave in self:
            users = leave.approval_advance_ids.mapped('approver_user_ids')
            leave.aa_approver_user_ids = [(6, 0, users.ids)]

    def _aa_get_mapped_approvers(self):
        self.ensure_one()
        emp = self.employee_id
        if not emp or not emp.department_id:
            return self.env['hr.employee']
        config = self.env['attendance_advance.approval_config'].search([
            ('request_department_id', '=', emp.department_id.id)
        ], order='sequence asc', limit=1)
        return config.approver_employee_ids if config else self.env['hr.employee']

    # def _aa_ensure_leave_approval_record(self):
    #     for leave in self:
    #         # Create only for Advanced Validation time off types
    #         if leave.validation_type != 'advanced':
    #             continue
    #         _logger.debug("_aa_ensure_leave_approval_record called for leave id=%s, employee=%s, dept=%s, type=%s",
    #                       leave.id, getattr(leave.employee_id, 'id', False),
    #                       getattr(leave.employee_id.department_id, 'id', False), leave.validation_type)
    #         # If record already exists, update approvers from mapping and continue
    #         approval = self.env['attendance_advance.leave_approval'].sudo().search([('leave_id', '=', leave.id)], limit=1)
    #         approvers = leave._aa_get_mapped_approvers()
    #         if approval:
    #             approval.sudo().write({
    #                 'department_id': leave.employee_id.department_id.id if leave.employee_id.department_id else False,
    #                 'approver_employee_ids': [(6, 0, approvers.ids)],
    #                 'approver_user_ids': [(6, 0, approvers.mapped('user_id').ids)],
    #             })
    #             _logger.info("Updated existing leave_approval (id=%s) for leave id=%s with approvers=%s",
    #                          approval.id, leave.id, approvers.ids)
    #         # Ensure container record exists
    #         if not approval:
    #             vals = {
    #                 'name': 'Time Off Approval',
    #                 'leave_id': leave.id,
    #                 'department_id': leave.employee_id.department_id.id if leave.employee_id.department_id else False,
    #                 'approver_employee_ids': [(6, 0, approvers.ids if approvers else [])],
    #                 'approver_user_ids': [(6, 0, approvers.mapped('user_id').ids if approvers else [])],
    #             }
    #             approval = self.env['attendance_advance.leave_approval'].sudo().create(vals)
    #             _logger.info("Created leave_approval id=%s for leave id=%s with approvers=%s",
    #                         approval.id, leave.id, approvers.ids if approvers else [])

    #         # Ensure per-approver requests exist when we have approvers
    #         if approvers:
    #             Request = self.env['attendance_advance.approval_request'].sudo()
    #             existing = Request.search([('leave_id', '=', leave.id)])
    #             existing_by_emp = {r.approver_employee_id.id: r for r in existing}
    #             # create missing
    #             for emp in approvers:
    #                 if emp.id not in existing_by_emp:
    #                     Request.create({
    #                         'name': 'Time Off Approval',
    #                         'leave_id': leave.id,
    #                         'department_id': leave.employee_id.department_id.id if leave.employee_id.department_id else False,
    #                         'approver_employee_id': emp.id,
    #                     })
    #             # remove extra (no longer approver)
    #             extra = existing.filtered(lambda r: r.approver_employee_id not in approvers)
    #             if extra:
    #                 extra.sudo().unlink()


    def _get_group_members(self, xml_id):
        group = self.env.ref(xml_id)                           # Load group
        users = group.users                                    # All users in group
        employees = users.mapped('employee_id').filtered(lambda e: e)  # Convert to employee records (skip empty)
        return users, employees



    def _get_leave_approvers(self):
        """Return employees & users needed for approval based on number of leave days."""
        days = int(self.number_of_days)
    
        manager_users = self.env.ref('adevx_hr_leave_rule.group_leave_manager').users
        hr_users = self.env.ref('adevx_hr_leave_rule.group_leave_hr').users
        md_users = self.env.ref('adevx_hr_leave_rule.group_leave_md').users
    
        manager_emps = manager_users.mapped('employee_id').filtered(lambda e: e)
        hr_emps = hr_users.mapped('employee_id').filtered(lambda e: e)
        md_emps = md_users.mapped('employee_id').filtered(lambda e: e)
    
        # <= 1 day → Manager only
        if days <= 1:
            return manager_emps, manager_users
    
        # 2 - 5 days → Manager + HR
        elif 2 <= days <= 5:
            return (manager_emps | hr_emps), (manager_users | hr_users)
    
        # > 5 days → Manager + HR + MD
        else:
            return (manager_emps | hr_emps | md_emps), (manager_users | hr_users | md_users)
    

    def _aa_ensure_leave_approval_record(self):
        for leave in self:
            if leave.validation_type != 'advanced':
                continue
    
            _logger.debug("_aa_ensure_leave_approval_record called for leave id=%s", leave.id)
    
            approval = self.env['attendance_advance.leave_approval'].sudo().search([
                ('leave_id', '=', leave.id)
            ], limit=1)
    
            # ✅ Get approvers based on leave length rule
            approver_emps, approver_users = leave._get_leave_approvers()
    
            if approval:
                approval.sudo().write({
                    'department_id': leave.employee_id.department_id.id if leave.employee_id.department_id else False,
                    'approver_employee_ids': [(6, 0, approver_emps.ids)],
                    'approver_user_ids': [(6, 0, approver_users.ids)],
                })
                _logger.info("Updated existing leave_approval id=%s for leave id=%s", approval.id, leave.id)
    
            # ✅ Create approval record if missing
            else:
                vals = {
                    'name': 'Time Off Approval',
                    'leave_id': leave.id,
                    'department_id': leave.employee_id.department_id.id if leave.employee_id.department_id else False,
                    'approver_employee_ids': [(6, 0, approver_emps.ids)],
                    'approver_user_ids': [(6, 0, approver_users.ids)],
                }
                approval = self.env['attendance_advance.leave_approval'].sudo().create(vals)
                _logger.info("Created leave_approval id=%s for leave id=%s", approval.id, leave.id)
    
            # ✅ Ensure per-approver requests exist
            Request = self.env['attendance_advance.approval_request'].sudo()
            existing = Request.search([('leave_id', '=', leave.id)])
            existing_by_emp = {r.approver_employee_id.id: r for r in existing}
    
            # Create missing
            for emp in approver_emps:
                if emp.id not in existing_by_emp:
                    Request.create({
                        'name': 'Time Off Approval',
                        'leave_id': leave.id,
                        'department_id': leave.employee_id.department_id.id if leave.employee_id.department_id else False,
                        'approver_employee_id': emp.id,
                    })
    
            # Remove extra
            extra = existing.filtered(lambda r: r.approver_employee_id not in approver_emps)
            if extra:
                extra.sudo().unlink()
    

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        try:
            rec._aa_ensure_leave_approval_record()
        except Exception:
            # Log exception so we can diagnose why approval creation failed without blocking leave creation
            _logger.exception('Error while ensuring leave approval record for leave id=%s', rec.id)
        return rec

    def write(self, vals):
        res = super().write(vals)
        # Re-evaluate mapping on type or employee changes
        if any(k in vals for k in ('holiday_status_id', 'employee_id')):
            try:
                self._aa_ensure_leave_approval_record()
            except Exception:
                _logger.exception('Error while updating leave approval records on write for leaves: %s', self.ids)
        return res
