from odoo import api, fields, models


class WorkSchedule(models.Model):
    _name = 'attendance_advance.work_schedule'
    _description = 'Work schedule (department / employee level)'


    name = fields.Char(required=True)
    department_id = fields.Many2one('hr.department', string='Department')
    employee_ids = fields.Many2many('hr.employee', string='Employees')
    schedule_line_ids = fields.One2many('attendance_advance.schedule_line', 'work_schedule_id', string='Schedule Lines')


    # Excuse / grace policy
    grace_in_minutes = fields.Integer(string='Grace Minutes (In)', default=0)
    grace_out_minutes = fields.Integer(string='Grace Minutes (Out)', default=0)
    min_late_entry_request = fields.Integer(string='Min Late Minutes To Request', default=0)
    monthly_limit_requests = fields.Integer(string='Monthly Late Appeal Limit (0 = Unlimited)', default=0)


    @api.onchange('department_id')
    def _onchange_department(self):
        if self.department_id:
            employees = self.env['hr.employee'].search([('department_id', '=', self.department_id.id)])
            self.employee_ids = [(6, 0, employees.ids)]