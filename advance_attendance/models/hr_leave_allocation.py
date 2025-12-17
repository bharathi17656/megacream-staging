from datetime import datetime, timedelta, time , date
import pytz
import logging
from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)



class HrLeaveAllocationExt(models.Model):
    _inherit = "hr.leave.allocation"

   
    @api.model
    def allocate_for_joining(self, employee):
        """Auto allocate leaves based on joining date and company leave policy."""

        contract = self.env['hr.contract'].search([('employee_id','=',employee.id),('state','=','open')])
        
        company = employee.company_id
        # join_date = employee.contract_id.date_start and fields.Date.from_string(employee.contract_id.date_start) or date.today()
        join_date = date.today()

        _logger.warning("this is the join date of this employee %s , %s", employee.name, join_date)

        # Define base yearly entitlement
        casual_per_year = 12
        sick_per_year = 12
        el_days = 0  # Not applicable initially

        # Determine monthly entitlement
        casual_per_month = casual_per_year / 12
        sick_per_month = sick_per_year / 12

        # Determine join month rule
        day = join_date.day
        if day <= 15:
            join_month_credit = 1.0  # full month credit
        elif 15 < day <= 20:
            join_month_credit = 0.5  # half month credit
        else:
            join_month_credit = 0.0  # no credit

        # Calculate remaining months including join month
        remaining_months = 12 - join_date.month + 1
        total_months_credit = join_month_credit + (remaining_months - 1)

        casual_alloc = round(total_months_credit * casual_per_month, 1)
        sick_alloc = round(total_months_credit * sick_per_month, 1)

        _logger.warning("calculated CL: %s, SL: %s, total months credited: %s", casual_alloc, sick_alloc, total_months_credit)

        leave_type_obj = self.env['hr.leave.type']
        for tname, days in (('CL', casual_alloc), ('SL', sick_alloc), ('EL', el_days)):
            lt = leave_type_obj.search([
                ('short_code', '=', tname),
                '|',
                ('company_id', '=', company.id),
                ('company_id', '=', False)
            ], limit=1)
            if lt and days > 0:
                _logger.warning("Creating initial allocation for %s (%s days)", tname, days)
                self.create({
                    'name': f'Initial allocation {tname}',
                    'employee_id': employee.id,
                    'holiday_status_id': lt.id,
                    'number_of_days': days,
                    'date_from': date(date.today().year, 1, 1),
                    'date_to': date(date.today().year, 12, 31),
                    'allocation_type': 'regular',
                    'employee_company_id': company.id,
                }).action_approve()
                

    
                

    @api.model
    def cron_allocate_existing_joins(self):

        employees = self.env['hr.employee'].search([])
        
        for emp in employees:
            contract = self.env['hr.contract'].search([('employee_id','=',emp.id),('state','=','open')])
            # naive guard: skip if any allocation exists for emp this year
            existing = self.search([('employee_id', '=', emp.id), ('create_date', '>=', fields.Date.to_string(date(date.today().year,1,1)))], limit=1)
            if not existing and contract.date_start:
                self.allocate_for_joining(emp)


    @api.model
    def cron_allocate_new_joins(self):
        """Cron that allocates for employees who joined in last day/week and not yet allocated"""
        employees = self.env['hr.employee'].search([('contract_id.date_start', '>=', fields.Date.to_string(fields.Date.context_today(self) - timedelta(days=7)))])
        for emp in employees:
            # naive guard: skip if any allocation exists for emp this year
            existing = self.search([('employee_id', '=', emp.id), ('create_date', '>=', fields.Date.to_string(date(date.today().year,1,1)))], limit=1)
            if not existing:
                self.allocate_for_joining(emp)
