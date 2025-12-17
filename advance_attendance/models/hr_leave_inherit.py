from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import timedelta, datetime

import logging

_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    leave_balance_details = fields.Text(string="Leave Balance Details", readonly=True)
    leave_Transfer_from = fields.Text(string="Leave Tranferred Details", readonly=True)
    
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

    def action_check_leave_balance(self):
        for leave in self:
            employee = leave.employee_id
            leave_types = self.env['hr.leave.type'].search([])

            result_lines = []
            for ltype in leave_types:
                allocation = ltype.get_allocation_data(employee, fields.Date.today())
                if ltype.requires_allocation == 'no':
                    balance_text = "Unlimited"
                else:
                    remaining = allocation[employee] and allocation[employee][0][1]['virtual_remaining_leaves'] or 0
                    balance_text = f"{remaining} Days Available"

                result_lines.append(f"{ltype.name}: {balance_text}")

            leave.leave_balance_details = "\n".join(result_lines)


  


    @api.constrains('request_date_from')
    def _check_intimation_period(self):
        for rec in self:
            # Run only when employee is applying (draft/requested stage)
            if rec.state not in ['draft', 'confirm']:
                continue

            if not rec.holiday_status_id or not rec.request_date_from:
                continue

            required_days = rec.holiday_status_id.x_intimate_before_days or 0
            today = fields.Date.today()

            if required_days:
                min_allowed_date = today + timedelta(days=required_days)

                if rec.request_date_from < min_allowed_date:
                    raise ValidationError(_(
                        f"You must apply for {rec.holiday_status_id.name} at least "
                        f"{required_days} day(s) in advance.\n"
                        f"Minimum allowed start date: {min_allowed_date.strftime('%d-%b-%Y')}"
                    ))

  

    @api.constrains('request_date_from', 'request_date_to')
    def _check_continuous_leave_policy(self):
        """Prevent employee from creating 4+ continuous days leave excluding special leave."""
        if self.env.context.get('skip_continuous_check'):
            return

        for leave in self:
            # Only check when employee is applying / requesting
            if leave.state not in ['draft', 'confirm']:
                continue

            # Skip for special leave
            if leave.is_special_leave:
                continue

            if not leave.request_date_from or not leave.request_date_to:
                continue

            employee = leave.employee_id

            work_schedule = self.env['attendance_advance.work_schedule'].search([
                '|',
                ('employee_ids', 'in', employee.id),
                ('department_id', '=', employee.department_id.id)
            ], limit=1)

            def is_non_working_or_leave(date):
                """
                Return True if this date should be counted as part of a
                continuous block: public holiday, non-working day (weekend /
                alt Saturday), or existing leave of this employee.
                """

                # 1) Public holiday (company calendar)
                public_holiday = self.env['resource.calendar.leaves'].search([
                    ('date_from', '<=', datetime.combine(date, datetime.min.time())),
                    ('date_to', '>=', datetime.combine(date, datetime.max.time())),
                ], limit=1)
                if public_holiday:
                    return True

                # 2) Existing leave on this date (other records)
                existing_leave = self.search([
                    ('employee_id', '=', employee.id),
                    ('request_date_from', '<=', date),
                    ('request_date_to', '>=', date),
                    ('id', '!=', leave.id),
                    # ('state', 'in', ['confirm', 'validate', 'validate1']),
                ], limit=1)
                if existing_leave:
                    return True

                # 3) Non-working day → weekend / alternate Saturday off
                #    If it's a working day (including 1st/3rd Saturday),
                #    we do NOT count it, it breaks the chain.
                if not self._is_working_day(date, work_schedule):
                    return True

                # 4) Otherwise → normal working day, no leave/holiday → chain breaks
                return False

            # -------------------------------
            # Count inside requested period
            # -------------------------------
            total_days = 0
            cursor = leave.request_date_from
            while cursor <= leave.request_date_to:
                total_days += 1
                cursor += timedelta(days=1)

            # --------------------------------------------
            # Count backwards (holidays, weekends, leaves)
            # --------------------------------------------
            cursor_back = leave.request_date_from - timedelta(days=1)
            while is_non_working_or_leave(cursor_back):
                total_days += 1
                cursor_back -= timedelta(days=1)

            # -------------------------------------------
            # Count forwards (holidays, weekends, leaves)
            # -------------------------------------------
            cursor_forward = leave.request_date_to + timedelta(days=1)
            while is_non_working_or_leave(cursor_forward):
                total_days += 1
                cursor_forward += timedelta(days=1)

            # Final decision
            if total_days >= 4:
                raise ValidationError(_(
                    "Your leave request cannot be submitted because it creates a continuous block of %s days.\n"
                    "Weekends, public holidays, alternate Saturdays, and adjacent leave requests are counted."
                ) % total_days)
                

    # # -------------------------------------------------------------------------
    # # Working Day Helper – handles alternate / custom Saturday logic
    # # -------------------------------------------------------------------------
    # def _is_working_day(self, date, work_schedule):
    #     """Check if date is working based on work schedule pattern."""
    #     if not work_schedule:
    #         # default: Mon–Fri working, Sat/Sun off
    #         return date.weekday() < 5

    #     weekday = str(date.weekday())  # Monday=0 ... Sunday=6

    #     schedule_line = work_schedule.schedule_line_ids.filtered(lambda l: l.day == weekday)
    #     if not schedule_line:
    #         # If no config found for that day, assume off
    #         return False

    #     schedule_line = schedule_line[0]

    #     if schedule_line.pattern_type == 'all':
    #         return True

    #     if schedule_line.pattern_type == 'alternate':
    #         # e.g. 1st & 3rd Saturdays as working (your current logic)
    #         if date.weekday() == 5:  # Saturday
    #             week_number = (date.day - 1) // 7 + 1
    #             # Here: 1st & 3rd are working; 2nd/4th/5th are off
    #             return week_number in [1, 3]
    #         # Other weekdays: Mon–Fri working
    #         return date.weekday() < 5

    #     if schedule_line.pattern_type == 'custom':
    #         # Parse alternate_pattern string like "1,3 work;2,4 off"
    #         pattern = schedule_line.alternate_pattern or ''
    #         week_number = (date.day - 1) // 7 + 1
    #         if f"{week_number} work" in pattern:
    #             return True
    #         elif f"{week_number} off" in pattern:
    #             return False
    #         # fallback to Mon–Fri working
    #         return date.weekday() < 5

    #     # Fallback: working
    #     return True



   
    
    def _is_working_day(self, date, work_schedule):
            """Check if date is working based on work schedule pattern"""
            if not work_schedule:
                # default: Mon–Fri working, Sat/Sun off
                return date.weekday() < 5
    
            weekday = str(date.weekday())  # e.g. Monday=0
    
            schedule_line = work_schedule.schedule_line_ids.filtered(lambda l: l.day == weekday)
            if not schedule_line:
                return False  # assume off day if no config found
    
            if schedule_line.pattern_type == 'all':
                return True
    
            if schedule_line.pattern_type == 'alternate':
                # Check if 1st/3rd Saturday logic applies
                if date.weekday() == 5:  # Saturday
                    week_number = (date.day - 1) // 7 + 1
                    return week_number in [1, 3]
                return date.weekday() < 5  # Mon–Fri working
    
            if schedule_line.pattern_type == 'custom':
                # Parse alternate_pattern string like "1,3 work;2,4 off"
                pattern = schedule_line.alternate_pattern or ''
                week_number = (date.day - 1) // 7 + 1
                if f"{week_number} work" in pattern:
                    return True
                elif f"{week_number} off" in pattern:
                    return False
                # fallback to standard
                return date.weekday() < 5
    
            return True




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

   


    # def action_validate(self, check_state=False):
    #     res = super(HrLeave, self).action_validate(check_state=check_state)

    #     for leave in self:
            
    #         # === 1️⃣ If Paid Leave selected → NO split logic ===
    #         if leave.paid_leave:
    #             continue

    #         leave_type = leave.holiday_status_id

    #         # If already CL, SL, or LOP → skip
    #         if leave_type.short_code in ['CL', 'SL', 'LOP']:
    #             continue

    #         employee = leave.employee_id
    #         requested_days = int(leave.number_of_days)
    #         start_date = leave.request_date_from

    #         def _get_balance(code):
    #             lt = self.env['hr.leave.type'].search([('short_code', '=', code)], limit=1)
    #             alloc = lt.get_allocation_data(employee, fields.Date.today())
    #             return alloc[employee] and alloc[employee][0][1]['virtual_remaining_leaves'] or 0

    #         cl_balance = int(_get_balance('CL'))
    #         sl_balance = int(_get_balance('SL'))

    #         remaining = requested_days
    #         daily_dates = [start_date + timedelta(days=i) for i in range(remaining)]
    #         allocations = []

    #         # CL Split
    #         if cl_balance > 0 and remaining > 0:
    #             use_cl = min(cl_balance, remaining)
    #             cl_type = self.env['hr.leave.type'].search([('short_code', '=', 'CL')], limit=1)
    #             allocations.append((cl_type.id, daily_dates[0], daily_dates[use_cl-1], use_cl))
    #             remaining -= use_cl
    #             daily_dates = daily_dates[use_cl:]

    #         # SL Split
    #         if sl_balance > 0 and remaining > 0:
    #             use_sl = min(sl_balance, remaining)
    #             sl_type = self.env['hr.leave.type'].search([('short_code', '=', 'SL')], limit=1)
    #             allocations.append((sl_type.id, daily_dates[0], daily_dates[use_sl-1], use_sl))
    #             remaining -= use_sl
    #             daily_dates = daily_dates[use_sl:]

    #         # Remaining → LOP
    #         if remaining > 0:
    #             lop_type = self.env['hr.leave.type'].search([('short_code', '=', 'LOP')], limit=1)
    #             allocations.append((lop_type.id, daily_dates[0], daily_dates[remaining-1], remaining))

    #         # === 2️⃣ Mark Original Leave as Auto-Refused ===
    #         leave.auto_refused = True
    #         leave.action_refuse()

    #         # === 3️⃣ Create New Split Leaves and Copy Special Flag ===
    #         new_records = self.env['hr.leave']


    #         transfer_text = "---System Generated Leave---\n"
    #         transfer_text += f"Original Requested: {requested_days} Day(s)\n"
    #         transfer_text += f"Processed on: {fields.Date.today()}\n\n"
    #         transfer_text += "Transferred Breakdown:\n"
            
    #         for lt_id, d_from, d_to, days in allocations:
    #             lt_name = self.env['hr.leave.type'].browse(lt_id).name
    #             transfer_text += f" - {days} Day(s) → {lt_name} ({d_from} to {d_to})\n"


    
    #         for lt_id, d_from, d_to, days in allocations:
    #             new_leave = self.env['hr.leave'].with_context(
    #                 leave_fast_create=True, 
    #                 skip_leave_validity=True, 
    #                 leave_skip_state_check=True
    #             ).create({
    #                 'employee_id': employee.id,
    #                 'holiday_status_id': lt_id,
    #                 'request_date_from': d_from,
    #                 'request_date_to': d_to,
    #                 'number_of_days': days,
    #                 'auto_created':True,
    #                 'state': 'validate',
    #                 'is_special_leave': leave.is_special_leave, 
    #                 'name':leave.name,
    #                 'leave_Transfer_from': f"Requested {leave.holiday_status_id.name} from: {employee.name}\n\n{transfer_text}"
    #             })
    #             new_records += new_leave
    #             leave_type_short = self.env['hr.leave.type'].browse(lt_id).short_code
    #             if leave_type_short == 'CL':
    #                 new_leave.write({'leave_reason': 'other'})

            

    #         # === 4️⃣ Link transferred records to original leave ===
    #         leave.transfer_leave_ids_str = ",".join(str(r.id) for r in new_records)

    #     return res
    
