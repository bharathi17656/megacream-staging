from odoo import models, fields, api
from datetime import time

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

    @api.depends("check_in", "check_out")
    def _compute_status(self):
        for rec in self:

            # 1️⃣ Miss In (check_out exists, check_in missing)
            if not rec.check_in and rec.check_out:
                rec.status = "Miss In"
                continue

            # 3️⃣ Late (both exist & check_in after 09:30)
            if rec.check_in:
                local_dt = fields.Datetime.context_timestamp(
                    rec, rec.check_in
                )
                if local_dt.time() > time(9, 30):
                    rec.status = "Late"
                    continue

            # 4️⃣ Present (both exist & on time)
            if rec.check_in:
                rec.status = "Present"






# from odoo import models, fields, api
#
# class HrEmployee(models.Model):
#     _inherit = "hr.employee"
#
#     x_studio_emp_id = fields.Char(string="Emp ID")
#
#
# class HrAttendance(models.Model):
#     _inherit = "hr.attendance"
#
#     status = fields.Char(
#         string="Status",
#         compute="_compute_status",
#         store=True,
#         readonly=True,
#     )
#
#     @api.depends("check_in")
#     def _compute_status(self):
#         for rec in self:
#             if rec.check_in:
#                 rec.status = "Present"
#             else:
#                 rec.status = "Absence"