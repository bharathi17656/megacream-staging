from odoo import api, fields, models


class HrLeaveRule(models.Model):
    _name = 'hr.leave.rule'
    _rec_name = 'name'
    _description = 'HR Leave Rule'

    name = fields.Char(string="Name", required=True)
    maximum_allocation = fields.Float(string="Maximum Allocation", required=True)
    allocation_unit = fields.Selection(string="Allocation Unit", selection=[
        ('hour', 'Hours'), ('day', 'Days')], required=True)

    time_off_request_rule = fields.Boolean(
        string="Time Off Request Rule", help="this Field to prevent employee to allocate Time off in previous periods")
    # time_off_request_before = fields.Float(string="Time Off Request Must Be Before")
    
    time_off_request_before_config_ids = fields.One2many(
        'hr.leave.rule.before.config',
        'leave_rule_id',
        string="Request Before Configurations"
    )

    maximum_time_off_each_request = fields.Float(string="Maximum Time Off For Each Request")

    start_time_off_allocation = fields.Boolean(
        string="Start Time-off Allocation",
        help="Allow employee To request time off after (Start Time-off Allocation After) from employee first contract date ")

    start_time_off_allocation_after = fields.Float(string="Start Time-off Allocation After")



    @api.model
    def get_required_before_days(self, leave_rule_id, requested_days):
        """Return required 'before days' based on number of requested leave days"""
        rule = self.browse(leave_rule_id)
        if not rule or not rule.exists():
            return 0.0

        configs = rule.time_off_request_before_config_ids.sorted('max_days')
        for config in configs:
            if requested_days <= config.max_days:
                return config.before_days

        # If requested days exceed all configured limits
        if configs:
            return configs[-1].before_days
        return 0.0


class HrLeaveRuleBeforeConfig(models.Model):
    _name = 'hr.leave.rule.before.config'
    _description = 'Leave Rule Request Before Configuration'

    leave_rule_id = fields.Many2one('hr.leave.rule', string="Leave Rule", ondelete='cascade')
    max_days = fields.Integer(string="Request Days <= ", required=True)
    before_days = fields.Integer(string="Must Be Requested Before (Days)", required=True)
