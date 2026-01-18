from odoo import api, fields, models


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    x_intimate_before_days = fields.Integer(
        string="Intimation (Days Before)",
        help="Number of days before leave start that the employee must apply. "
             "Example: 0 = same day, 1 = 1 day before, etc.",
        default=0
    )
    
    max_continuous_days = fields.Integer(string='Max Continuous Days', default=0)
    
    short_code = fields.Char(
        string="Short Code",
        size=3,
        help="Short identifier for the leave type (e.g. CL, SL, EL)"
    )
    sandwich_rule = fields.Boolean(string='Sandwich Rule (count non-working days)', default=False)

    counts_non_working_days = fields.Boolean(string='Counts Non-working Days', default=False)

    


