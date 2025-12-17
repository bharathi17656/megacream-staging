from odoo import api, fields, models, _
from datetime import date
from odoo.exceptions import UserError


class AutoAllocationConfig(models.Model):
    _name = 'attendance_advance.auto_allocation_config'
    _description = 'Automatic Time Off Allocation Configuration'

    name = fields.Char(required=True)
    timeoff_type_id = fields.Many2one('hr.leave.type', string="Time Off Type", required=True)
    days_allocated = fields.Float(string="Days to Allocate", required=True)
    prorate_by_join_date = fields.Boolean(string="Prorate by Join Date")
    allocation_mode = fields.Selection([
        ('existing_only', 'Existing Employees'),
        ('new_only', 'New Employees'),
        ('both', 'All Employees')
    ], default='both', required=True)
    carry_forward = fields.Boolean(string="Carry Forward Remaining Days")
    is_active = fields.Boolean(default=True)
    allocation_reason = fields.Text(string="Reason / Note")

    def action_run_allocation(self):
        """Manual button to trigger auto allocation"""
        created_allocs = self._run_allocation_process()
        raise UserError(_("%s allocations created successfully.") % len(created_allocs))

    @api.model
    def _cron_auto_allocate(self):
        """Daily cron to allocate leaves automatically"""
        configs = self.search([('is_active', '=', True)])
        for config in configs:
            config._run_allocation_process()

    def _run_allocation_process(self):
        """Core logic shared by manual button and cron"""
        created = []
        Employee = self.env['hr.employee']
        Allocation = self.env['hr.leave.allocation'].sudo()  # ensure access rights
    
        today = fields.Date.context_today(self)
    
        for config in self:
            domain = [('active', '=', True)]
            if config.allocation_mode == 'new_only':
                domain.append(('contract_id.date_start', '>=', today.replace(day=1)))
            elif config.allocation_mode == 'existing_only':
                domain.append(('contract_id.date_start', '<', today))
    
            employees = Employee.search(domain)
            for emp in employees:
                # avoid duplicates
                existing_alloc = Allocation.search([
                    ('employee_id', '=', emp.id),
                    ('holiday_status_id', '=', config.timeoff_type_id.id),
                    ('state', '!=', 'refuse')
                ], limit=1)
                if existing_alloc:
                    continue
    
                days = config.days_allocated
                if config.prorate_by_join_date and emp.contract_id and emp.contract_id.date_start:
                    months_worked = max(1, 12 - emp.contract_id.date_start.month + 1)
                    days = round((config.days_allocated / 12) * months_worked, 1)
    
                alloc = Allocation.create({
                    'name': f'Auto Allocation - {config.timeoff_type_id.name}',
                    'holiday_status_id': config.timeoff_type_id.id,
                    'number_of_days': days,
                    'employee_id': emp.id,
                    'notes': config.allocation_reason or 'Automated allocation from Attendance Advance',
                })
               
                alloc.action_approve()
                created.append(alloc.id)
    
     
        return created
