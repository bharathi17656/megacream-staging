from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    x_studio_emp_id = fields.Char(string="Emp ID")

    
class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    status = fields.Char(
        string="Status",
        compute="_compute_status",
        store=True,
        readonly=True,
    )

    @api.depends("check_in")
    def _compute_status(self):
        for rec in self:
            if rec.check_in:
                rec.status = "Present"
            else:
                rec.status = "Absence"