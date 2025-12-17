from datetime import timedelta, date 
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    is_leave_manager_approved = fields.Boolean("Manager Approved", default=False)
    is_leave_hr_approved = fields.Boolean("HR Approved", default=False)
    is_leave_md_approved = fields.Boolean("MD Approved", default=False)

    approval_level = fields.Selection([
        ('manager', 'PR'),
        ('hr', 'PM & RM'),
        ('md', 'MD')
    ], string="Approval Level", compute="_compute_approval_level", store=True)

    show_approval_button = fields.Boolean(
        string="Show Approval Button",
        compute="_compute_show_approval_button",
        default=False
    )

    x_is_paid_override = fields.Boolean(
        string="Paid Override (HR Use Only)",
        help="If ticked, this leave is treated as Paid even if it's Unpaid (LOP).",
        default=False
    )


    @api.depends('number_of_days')
    def _compute_approval_level(self):
        for rec in self:
            if rec.number_of_days <= 1 and not rec.is_special_leave :
                rec.approval_level = 'manager'
            elif  rec.number_of_days >= 2 and not rec.is_special_leave:
                rec.approval_level = 'hr'
            elif rec.is_special_leave:
                rec.approval_level = 'md'


    @api.depends('approval_level', 'is_leave_manager_approved', 'is_leave_hr_approved', 'is_leave_md_approved')
    def _compute_show_approval_button(self):
        for rec in self:
            user = rec.env.user
            rec.show_approval_button = False

            if rec.state not in ['confirm', 'validate1', 'validate']:  # Don't show after final approval
                continue

            # Manager Approval Button
            if rec.approval_level in ['manager','hr'] and not rec.is_leave_manager_approved:
                rec.show_approval_button = user.has_group('adevx_hr_leave_rule.group_leave_manager')

            
            elif rec.approval_level in ['hr'] and rec.is_leave_manager_approved and not rec.is_leave_hr_approved:
                rec.show_approval_button = user.has_group('adevx_hr_leave_rule.group_leave_hr')

            # MD Approval Button (last)
            elif rec.approval_level == 'md' :
                rec.show_approval_button = user.has_group('adevx_hr_leave_rule.group_leave_md')

            # Always allow admin
            if user.has_group('adevx_hr_leave_rule.group_leave_super_admin'):
                rec.show_approval_button = True



    def action_validate(self,check_state):
        self.ensure_one()
        user = self.env.user
        
        if not user.has_group('adevx_hr_leave_rule.group_leave_super_admin') :
            if user.has_group('adevx_hr_leave_rule.group_leave_md') and self.approval_level in ['md']:
                self.is_leave_md_approved = True
                return super(HrLeave, self).action_validate(check_state)
                
            if user.has_group('adevx_hr_leave_rule.group_leave_manager') and self.approval_level in ['manager']:
                self.is_leave_manager_approved = True
                return super(HrLeave, self).action_validate(check_state)
                
            if user.has_group('adevx_hr_leave_rule.group_leave_manager') and self.approval_level in ['hr']:
                if not self.is_leave_manager_approved :
                    self.is_leave_manager_approved = True
                    if not self.is_leave_hr_approved:
                        self.env['bus.bus']._sendone(
                                self.env.user.partner_id,
                                'simple_notification',
                                {
                                    'type': 'warning',
                                    'title': "Status: Approved",
                                    'message': _("This request has received Project Manager approval and is pending Resource Manager approval'."),
                                }
                            )
                  
                    
                elif not self.is_leave_hr_approved :
                    raise UserError("This request has already received Project Manager approval and is pending Resource Manager approval.")
    
            if user.has_group('adevx_hr_leave_rule.group_leave_hr') and self.approval_level in ['hr']:
                if not self.is_leave_hr_approved :
                    self.is_leave_hr_approved = True
                    if not self.is_leave_manager_approved :
                        self.env['bus.bus']._sendone(
                                self.env.user.partner_id,
                                'simple_notification',
                                {
                                    'type': 'warning',
                                    'title': "Status: Approved",
                                    'message': _("This request has received Resource Manager approval and is pending Project Resource approval'."),
                                }
                            )
                    
                    
                elif not self.is_leave_manager_approved :
                    raise UserError("This request has already received Resource Manager approval and is pending Project Manager approval.")
                    
                    
            if self.approval_level in ['hr'] :
                if self.is_leave_hr_approved and self.is_leave_manager_approved :
                    return super(HrLeave, self).action_validate(check_state)
        else:
             return super(HrLeave, self).action_validate(check_state)


    def action_refuse(self):
        self.ensure_one()
        self.is_leave_md_approved = False
        self.is_leave_hr_approved = False
        self.is_leave_manager_approved = True
        return super(HrLeave, self).action_refuse()
        
        

            
            
 
