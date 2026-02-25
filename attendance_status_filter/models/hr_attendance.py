from odoo import models, fields, api
from datetime import time

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    x_studio_emp_id = fields.Char(string="Emp ID")


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    status = fields.Selection(
        [
            ("present", "Present"),
            ("late", "Late"),
            ("miss_out", "Miss Out"),
            ("absent", "Absent"),
        ],
        string="Status",
        compute="_compute_status",
        store=True,
        readonly=True,
    )

    @api.depends("check_in", "check_out")
    def _compute_status(self):
        for rec in self:

            # Both missing
            if not rec.check_in and not rec.check_out:
                rec.status = "absent"

            # Either check_in missing OR check_out missing
            elif not rec.check_in or not rec.check_out:
                rec.status = "miss_out"

            # Late check_in (after 9:30 AM)
            else:
                local_dt = fields.Datetime.context_timestamp(rec, rec.check_in)

                if local_dt.time() > time(9, 30):
                    rec.status = "late"
                else:
                    rec.status = "present"





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