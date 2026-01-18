from odoo import api, fields, models


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    max_request_as_per = fields.Integer(string="Max Request In Per Request")
    allocation_unit = fields.Selection(string="Before Unit", selection=[
        ('hour', 'Hours'), ('day', 'Days')], required=True)
    time_off_request_before = fields.Integer(string="Time Off Request Must Be Before")
    short_code = fields.Char(
        string="Short Code",
        size=3,
        help="Short identifier for the leave type (e.g. CL, SL, EL)"
    )
    


