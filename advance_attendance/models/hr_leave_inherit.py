from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import timedelta, datetime

import logging

_logger = logging.getLogger(__name__)



class HrLeave(models.Model):
    _inherit = 'hr.leave'

    leave_Transfer_from = fields.Text(string="Leave Transferred Details", readonly=True)
    is_special_leave = fields.Boolean(string="Special Leave")

    auto_refused = fields.Boolean("Auto Refused", default=False)
    auto_created = fields.Boolean("Auto Created", default=False)
    transfer_leave_ids_str = fields.Char(string="Transferred Leave IDs")
    paid_leave = fields.Boolean("Paid Leave")

    leave_reason = fields.Selection([
        ('personal', 'Personal work'),
        ('family', 'Family commitment'),
        ('travel', 'Travel or out-of-town errand'),
        ('home_repair', 'Home maintenance or repair'),
        ('official_doc', 'Official documentation work'),
        ('child_related', 'Child-related reasons'),
        ('mental_health', 'Mental health / personal recharge'),
        ('other', 'Other reason'),
    ], string="Reason for Leave / Break")

    # --------------------------------------------------
    # Intimation Period Check
    # --------------------------------------------------

    @api.constrains('request_date_from')
    def _check_intimation_period(self):
        for rec in self:
            if rec.state not in ['draft', 'confirm']:
                continue

            if not rec.holiday_status_id or not rec.request_date_from:
                continue

            required_days = rec.holiday_status_id.x_intimate_before_days or 0
            if not required_days:
                continue

            today = fields.Date.today()
            min_allowed_date = today + timedelta(days=required_days)

            if rec.request_date_from < min_allowed_date:
                raise ValidationError(_(
                    "You must apply for %(leave)s at least %(days)s day(s) in advance.\n"
                    "Minimum allowed start date: %(date)s"
                ) % {
                    'leave': rec.holiday_status_id.name,
                    'days': required_days,
                    'date': min_allowed_date.strftime('%d-%b-%Y'),
                })

    # --------------------------------------------------
    # Continuous Leave Policy (REFINED)
    # --------------------------------------------------

    @api.constrains('request_date_from', 'request_date_to')
    def _check_continuous_leave_policy(self):
        """Prevent employee from creating 4+ continuous days leave."""
        if self.env.context.get('skip_continuous_check'):
            return

        for leave in self:
            if leave.state not in ['draft', 'confirm']:
                continue

            if leave.is_special_leave:
                continue

            if not leave.request_date_from or not leave.request_date_to:
                continue

            employee = leave.employee_id
            calendar = employee.resource_calendar_id

            def is_non_working_or_leave(date):
                """
                True if:
                - Public holiday
                - Existing leave
                - Non-working day based on resource calendar
                """

                # 1) Public holiday
                public_holiday = self.env['resource.calendar.leaves'].search([
                    ('calendar_id', '=', calendar.id),
                    ('date_from', '<=', datetime.combine(date, datetime.min.time())),
                    ('date_to', '>=', datetime.combine(date, datetime.max.time())),
                ], limit=1)
                if public_holiday:
                    return True

                # 2) Existing leave
                existing_leave = self.search([
                    ('employee_id', '=', employee.id),
                    ('request_date_from', '<=', date),
                    ('request_date_to', '>=', date),
                    ('id', '!=', leave.id),
                ], limit=1)
                if existing_leave:
                    return True

                # 3) Non-working day (calendar-driven)
                if calendar and not calendar._works_on_date(date):
                    return True

                # 4) Otherwise → working day
                return False

            # -------------------------------
            # Count requested period
            # -------------------------------
            total_days = 0
            cursor = leave.request_date_from
            while cursor <= leave.request_date_to:
                total_days += 1
                cursor += timedelta(days=1)

            # -------------------------------
            # Count backwards
            # -------------------------------
            cursor = leave.request_date_from - timedelta(days=1)
            while is_non_working_or_leave(cursor):
                total_days += 1
                cursor -= timedelta(days=1)

            # -------------------------------
            # Count forwards
            # -------------------------------
            cursor = leave.request_date_to + timedelta(days=1)
            while is_non_working_or_leave(cursor):
                total_days += 1
                cursor += timedelta(days=1)

            if total_days >= 4:
                raise ValidationError(_(
                    "Your leave request cannot be submitted because it creates a continuous block of %s days.\n"
                    "Weekends, public holidays, alternate Saturdays, and adjacent leave requests are counted."
                ) % total_days)



    @api.constrains('date_from', 'date_to', 'employee_id')
    def _check_validity(self):
        if self.env.context.get('skip_leave_validity'):
            return
        return super()._check_validity()




    
    def _get_cs_balances_for_request(self, employee, start_date, requested_days):
        self.ensure_one()
    
        def _get_balance(code):
            leave_type = self.env['hr.leave.type'].search([('short_code', '=', code)], limit=1)
            if not leave_type:
                return 0
            alloc = leave_type.get_allocation_data(employee, fields.Date.today())
            _logger.warning("get balance alloc  details -------------------------- %s", alloc)
            return alloc.get(employee, []) and alloc[employee][0][1].get('virtual_remaining_leaves', 0) or 0
    
        cl_total = int(_get_balance('CL'))
        sl_total = int(_get_balance('SL'))
    
        daily_dates = [start_date + timedelta(days=i) for i in range(int(requested_days))]
    
        def _get_valid_allocation_range(code):
            leave_type = self.env['hr.leave.type'].search([('short_code', '=', code)], limit=1)
            if not leave_type:
                return None, None
            allocation = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', leave_type.id),
                ('state', '=', 'validate'),
            ], order="id desc", limit=1)
            return allocation.date_from, allocation.date_to
    
        cl_from, cl_to = _get_valid_allocation_range('CL')
        sl_from, sl_to = _get_valid_allocation_range('SL')
    
        # 🔥 FIXED LOGIC: Accept open-ended allocations
        valid_cl_dates = [d for d in daily_dates if cl_from and (not cl_to or cl_from <= d <= cl_to)]
        valid_sl_dates = [d for d in daily_dates if sl_from and (not sl_to or sl_from <= d <= sl_to)]
    
        cl_balance = min(cl_total, len(valid_cl_dates))
        sl_balance = min(sl_total, len(valid_sl_dates))
    
        _logger.warning("FINAL BALANCE (Effective): CL=%s SL=%s", cl_balance, sl_balance)
    
        return cl_balance, sl_balance

            



    def action_validate(self, check_state=False):
        res = super(HrLeave, self).action_validate(check_state=check_state)

        
    
        for leave in self:
            
            # === 1️⃣ If Paid Leave selected → NO split logic ===
            if leave.paid_leave:
                continue
    
            leave_type = leave.holiday_status_id
    
            # If already CL, SL, or LOP → skip
            if leave_type.short_code in ['CL', 'SL', 'LOP']:
                continue
    
            employee = leave.employee_id
            requested_days = int(leave.number_of_days)
            start_date = leave.request_date_from
    

            # 🔹 Get CL / SL balance just for this request window
            cl_balance, sl_balance = self._get_cs_balances_for_request(
                employee=employee,
                start_date=start_date,
                requested_days=requested_days,
            )
            _logger.warning("balance para details -------------------------- %s , %s , %s",employee,start_date,requested_days)
          
            _logger.warning("balance details -------------------------- %s , %s",cl_balance,sl_balance)
            
            remaining = requested_days
            daily_dates = [start_date + timedelta(days=i) for i in range(remaining)]
            allocations = []
    
            # CL Split
            if cl_balance > 0 and remaining > 0:
                use_cl = min(cl_balance, remaining)
                cl_type = self.env['hr.leave.type'].search([('short_code', '=', 'CL')], limit=1)
                allocations.append((cl_type.id, daily_dates[0], daily_dates[use_cl-1], use_cl))
                remaining -= use_cl
                daily_dates = daily_dates[use_cl:]
    
            # SL Split
            if sl_balance > 0 and remaining > 0:
                use_sl = min(sl_balance, remaining)
                sl_type = self.env['hr.leave.type'].search([('short_code', '=', 'SL')], limit=1)
                allocations.append((sl_type.id, daily_dates[0], daily_dates[use_sl-1], use_sl))
                remaining -= use_sl
                daily_dates = daily_dates[use_sl:]
    
            # Remaining → LOP
            if remaining > 0:
                lop_type = self.env['hr.leave.type'].search([('short_code', '=', 'LOP')], limit=1)
                allocations.append((lop_type.id, daily_dates[0], daily_dates[remaining-1], remaining))
    
            # === 2️⃣ Mark Original Leave as Auto-Refused ===
            leave.auto_refused = True
            leave.action_refuse()
    
            # === 3️⃣ Create New Split Leaves and Copy Special Flag ===
            new_records = self.env['hr.leave']
    
            transfer_text = "---System Generated Leave---\n"
            transfer_text += f"Original Requested: {requested_days} Day(s)\n"
            transfer_text += f"Processed on: {fields.Date.today()}\n\n"
            transfer_text += "Transferred Breakdown:\n"
            
            for lt_id, d_from, d_to, days in allocations:
                lt_name = self.env['hr.leave.type'].browse(lt_id).name
                transfer_text += f" - {days} Day(s) → {lt_name} ({d_from} to {d_to})\n"
    
    
            for lt_id, d_from, d_to, days in allocations:
                new_leave = self.env['hr.leave'].with_context(
                    leave_fast_create=True, 
                    skip_leave_validity=True, 
                    leave_skip_state_check=True
                ).create({
                    'employee_id': employee.id,
                    'holiday_status_id': lt_id,
                    'request_date_from': d_from,
                    'request_date_to': d_to,
                    'number_of_days': days,
                    'auto_created':True,
                    'state': 'validate',
                    'is_special_leave': leave.is_special_leave, 
                    'name':leave.name,
                    'leave_Transfer_from': f"Requested {leave.holiday_status_id.name} from: {employee.name}\n\n{transfer_text}"
                })
                new_records += new_leave
    
                # Set reason if CL
                leave_type_short = self.env['hr.leave.type'].browse(lt_id).short_code
                if leave_type_short == 'CL':
                    new_leave.write({'leave_reason': 'other'})
    
    
            # === 4️⃣ Link transferred records to original leave ===
            leave.transfer_leave_ids_str = ",".join(str(r.id) for r in new_records)
    
        return res

   

