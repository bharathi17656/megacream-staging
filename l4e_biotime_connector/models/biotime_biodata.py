from odoo import models, fields

class BiotimeBiodata(models.Model):
    _name = "biotime.biodata"
    _description = "Biotime Biodata"

    biotime_id = fields.Integer(index=True)
    employee_name = fields.Char()
    emp_code = fields.Char(index=True)
    bio_type = fields.Integer()
    bio_no = fields.Integer()
    bio_index = fields.Integer()
    bio_tmp = fields.Text()
    major_ver = fields.Char()
    update_time = fields.Datetime()

    employee_id = fields.Many2one(
        "hr.employee",
        string="Odoo Employee",
        ondelete="set null"
    )
