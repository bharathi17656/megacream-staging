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

            # No Check In
            if not rec.check_in:
                rec.status = "Absence"

            # Miss In (Check Out exists but no Check In)
            elif rec.check_out and not rec.check_in:
                rec.status = "Miss In"

            # Late (After 09:30 AM)
            elif rec.check_in:
                # Convert UTC to user timezone
                local_dt = fields.Datetime.context_timestamp(rec, rec.check_in)

                if local_dt.time() > time(9, 30):
                    rec.status = "Late"
                else:
                    rec.status = "Present"

            else:
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