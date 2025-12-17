from odoo import api, fields, models


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    leave_rule_id = fields.Many2one(comodel_name="hr.leave.rule", string="Leave Rule", required=False)
