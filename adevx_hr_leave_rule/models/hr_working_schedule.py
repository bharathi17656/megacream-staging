# models/hr_working_schedule.py
from odoo import api, fields, models


class ResourceCalendar(models.Model):
    """
    Extend the Working Schedule (resource.calendar) with an 'Employee Group Rule'
    that controls how LOP (Loss of Pay) and overtime/double-pay are computed
    on the payslip for employees assigned to this schedule.

    In Odoo 19, the working schedule is linked directly on hr.employee via
    resource_calendar_id, so this is the right place for group-level rules.
    """
    _inherit = 'resource.calendar'

    employee_group_rule = fields.Selection(
        selection=[
            ('group_1', 'Group 1 – Mon–Sat | 1 CL | 12 Holidays | Extra = LOP'),
            ('group_2', 'Group 2 – Mon–Sat | 1 CL | 12 Holidays | Sunday Work = No LOP | 7-Day = Double Pay'),
            ('group_3', 'Group 3 – Mon–Sat | No CL | 12 Holidays | Sunday Work = No LOP | 7-Day = Double Pay'),
            ('group_4', 'Group 4 – All Days Working | Any Leave = LOP | No Festival Holidays'),
        ],
        string='Employee Group Rule',
        help=(
            "Defines LOP and overtime rules for employees on this working schedule.\n\n"
            "Group 1: Mon-Sat, 1 Casual Leave/month, 12 festival holidays paid. "
            "Any extra absence = LOP.\n\n"
            "Group 2: Mon-Sat, 1 Casual Leave/month, 12 festival holidays paid. "
            "If employee takes a weekday leave but works on Sunday = no LOP (offset). "
            "If employee works all 7 days in a week = Sunday & festival days = Double Pay.\n\n"
            "Group 3: Same as Group 2 but NO casual leave allowance.\n\n"
            "Group 4: All 7 days are working days. Any absence = LOP. "
            "Yearly festival holidays are NOT applicable."
        )
    )
