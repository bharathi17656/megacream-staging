from odoo import fields, models




class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

  
    short_code = fields.Char(string="Leave Short Code", help="Used for policy matching, e.g. SL, CL, EL, LOP")
    
    x_intimate_before_days = fields.Integer(
        string="Intimation (Days Before)",
        help="Number of days before leave start that the employee must apply. "
             "Example: 0 = same day, 1 = 1 day before, etc.",
        default=0
    )
    
    max_continuous_days = fields.Integer(string='Max Continuous Days', default=0)
    sandwich_rule = fields.Boolean(string='Sandwich Rule (count non-working days)', default=False)

    counts_non_working_days = fields.Boolean(string='Counts Non-working Days', default=False)

