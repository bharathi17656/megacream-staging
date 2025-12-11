from odoo import api, fields, models

class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    normal_working_hours = fields.Float(
        string='Normal Worked Hours',
        compute='_compute_normal_worked_hours',
        store=True,
        readonly=True
    )

    project_id = fields.Many2one('project.project', string='Project')
    task_id = fields.Many2one('project.task', string='Task')

    @api.depends('check_in', 'check_out', 'worked_hours', 'validated_overtime_hours')
    def _compute_normal_worked_hours(self):
        for rec in self:
            if rec.worked_hours:
                if rec.validated_overtime_hours and rec.worked_hours > 10:
                    rec.normal_working_hours = rec.worked_hours - rec.validated_overtime_hours
                else:
                    rec.normal_working_hours = rec.worked_hours
            else:
                rec.normal_working_hours = 0.0



class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    tra_wage = fields.Float(string="TRA", compute="_compute_allowances", store=True)
    hra_wage = fields.Float(string="HRA", compute="_compute_allowances", store=True)
    tla_wage = fields.Float(string="TLA", compute="_compute_allowances", store=True)
    fda_wage = fields.Float(string="FDA", compute="_compute_allowances", store=True)

    @api.depends('line_ids.total')
    def _compute_allowances(self):
        line_values = (self._origin)._get_line_values([
            'TRA', 'HRA', 'TLA', 'FDA'
        ])
        for payslip in self:
            payslip.tra_wage = line_values['TRA'][payslip._origin.id]['total'] if 'TRA' in line_values else 0.0
            payslip.hra_wage = line_values['HRA'][payslip._origin.id]['total'] if 'HRA' in line_values else 0.0
            payslip.tla_wage = line_values['TLA'][payslip._origin.id]['total'] if 'TLA' in line_values else 0.0
            payslip.fda_wage = line_values['FDA'][payslip._origin.id]['total'] if 'FDA' in line_values else 0.0

