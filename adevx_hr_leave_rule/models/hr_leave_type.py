from odoo import api, fields, models


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    maximum_allocation = fields.Float(string="Maximum Allocation")
    allocation_unit = fields.Selection(string="Allocation Unit", selection=[
        ('hour', 'Hours'), ('day', 'Days')], required=True)
    time_off_request_before = fields.Float(string="Time Off Request Must Be Before")

