from odoo import api, models, fields, _
from odoo.exceptions import UserError


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    state = fields.Selection([
        ('confirm', 'To Verify'),
        ('validate', 'Verified'),
        ('validate1', 'Approved'),
        ('refuse', 'Refused')],
        string='Status', readonly=True, tracking=True, copy=False, default='confirm',
        help="The status is set to 'To Submit', when an allocation request is created."
             "\nThe status is 'To Approve', when an allocation request is confirmed by user."
             "\nThe status is 'Refused', when an allocation request is refused by manager."
             "\nThe status is 'Approved', when an allocation request is approved by manager.")

    def action_draft(self):
        if any(holiday.state not in ['validate', 'refuse'] for holiday in self):
            raise UserError(
                _('Allocation request state must be "Refused" or "Approve" in order to be reset to draft.'))
        self.write({
            'state': 'confirm',
        })
        # linked_requests = self.mapped('linked_request_ids')
        # if linked_requests:
        #     linked_requests.action_draft()
        #     linked_requests.unlink()
        # self.activity_update()
        return True

    @api.constrains('holiday_status_id', 'number_of_days_display', 'number_of_hours_display')
    def check_holiday_status_duration(self):
        for rec in self:
            # ✅ Skip if current user is a manager or HR officer
            if rec.env.user.has_group('hr_holidays.group_hr_holidays_manager') or \
               rec.env.user.has_group('hr.group_hr_manager'):
                # Manager is allowed to override the rule
                continue

            current_date = fields.Date.today()
            leave_rule = rec.holiday_status_id.leave_rule_id
            if not leave_rule:
                continue

            # 🧩 3. Start Time-Off Allocation Rule (based on contract)
            if leave_rule.start_time_off_allocation:
                contract = rec.employee_id.contract_id
                contract_date = getattr(contract, 'first_contract_date', None)
                if not contract_date:
                    raise UserError(
                        f"Employee {rec.employee_id.name} does not have a valid contract start date."
                    )

                diff = relativedelta(current_date, contract_date)
                num_of_months = (diff.years * 12) + diff.months

                if num_of_months < leave_rule.start_time_off_allocation_after:
                    raise UserError(
                        f"Employee {rec.employee_id.name} can request time off only after "
                        f"{leave_rule.start_time_off_allocation_after} months from contract date.\n"
                        f"Current duration: {num_of_months} months."
                    )
