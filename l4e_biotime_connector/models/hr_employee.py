from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    biotime_emp_code = fields.Char(
        string="Biotime Employee Code",
        index=True
    )
