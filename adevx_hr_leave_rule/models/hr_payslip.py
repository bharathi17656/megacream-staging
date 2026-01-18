# models/hr_payslip.py
from odoo import models, fields, api
from datetime import timedelta, time , datetime
import math
import calendar
import logging


_logger = logging.getLogger(__name__)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    unpaid_amount = fields.Float(string="Unpaid Amount", readonly=True)
    unpaid_days = fields.Float(string="Unpaid Days", readonly=True)
    paid_days = fields.Float(string="Paid Days", readonly=True)
    paid_amount = fields.Float(string="Paid Amount", readonly=True)
    total_days_in_month = fields.Float(string="Total Days in Month", readonly=True)
    total_working_days_in_month = fields.Float(string="Total Working Days in Month", readonly=True)

    def compute_sheet(self):
        WorkEntryType = self.env['hr.work.entry.type']
        Attendance = self.env['hr.attendance']
        Leave = self.env['hr.leave']

        def _get_or_create(code, name):
            rec = WorkEntryType.search([('code', '=', code)], limit=1)
            if not rec:
                rec = WorkEntryType.create({'name': name, 'code': code})
            return rec

       

        for payslip in self:
            contract = payslip.version_id
            employee = contract.employee_id if contract else payslip.employee_id
            if not contract or not employee:
                continue

         
            # CASE 1: If work entry source IS calendar → DO NOT rebuild lines
          
            if contract.work_entry_source == 'calendar':

                worked_lines = payslip.worked_days_line_ids
                input_lines = payslip.input_line_ids


                date_from = payslip.date_from
                date_to = payslip.date_to
            
                # Build all dates in range
                start_dt = fields.Date.from_string(date_from)
                end_dt = fields.Date.from_string(date_to)
                all_days = []
                current_day = start_dt
                while current_day <= end_dt:
                    all_days.append(current_day)
                    current_day += timedelta(days=1)


                # Find all Saturdays
                saturdays = [d for d in all_days if d.weekday() == 5]
            
                # Identify unwanted Saturdays: 2nd, 4th, and possible 5th
                unwanted_saturdays = []
                if len(saturdays) >= 2:
                    unwanted_saturdays.append(saturdays[1])  # 2nd Saturday
                if len(saturdays) >= 4:
                    unwanted_saturdays.append(saturdays[3])  # 4th Saturday
                if len(saturdays) >= 6:
                    unwanted_saturdays.append(saturdays[5])  
                if len(saturdays) >= 8:
                    unwanted_saturdays.append(saturdays[7])  

                work_entries = self.env['hr.work.entry'].search([
                    ('employee_id', '=', payslip.employee_id.id),
                    ('date', '>=', date_from),
                    ('date', '<=', date_to),
                ])
            
                for entry in work_entries:
                    entry_date = fields.Date.from_string(entry.date)
                    if entry_date in unwanted_saturdays:
                        entry.unlink()
                        
                work_entries = self.env['hr.work.entry'].search([
                    ('employee_id', '=', payslip.employee_id.id),
                    ('date', '>=', date_from),
                    ('date', '<=', date_to),
                ])
                
                for entry in work_entries :
                    if entry.work_entry_type_id.code == 'OVERTIME':
                        entry.unlink()

                # -----------------------------------------------------------
                # REFRESH worked_days_line_ids after removing Saturday entries
                # -----------------------------------------------------------
                payslip.worked_days_line_ids.unlink()  # Clear existing lines
                
                new_work_entries = self.env['hr.work.entry'].search([
                    ('employee_id', '=', payslip.employee_id.id),
                    ('date', '>=', date_from),
                    ('date', '<=', date_to)
                ])
                
                # Group entries by work entry type
                grouped = {}
                
                for entry in new_work_entries:
                    code = entry.work_entry_type_id.code
                    if code not in grouped:
                        grouped[code] = {
                            'name': entry.work_entry_type_id.name,
                            'sequence': 1,
                            'code': code,
                            'number_of_days': 0,
                            'number_of_hours': 0,
                            'version_id': contract.id,
                            'work_entry_type_id': entry.work_entry_type_id.id,
                        }
                
                    # Increment grouped values
                    grouped[code]['number_of_days'] += 1
                    grouped[code]['number_of_hours'] += 8  # Default 8 hours (change if needed)
                
                # Insert grouped values back in payslip
                payslip.worked_days_line_ids = [(0, 0, vals) for vals in grouped.values()]
                
                # 🔁 IMPORTANT: use the NEW records, not the deleted ones
                worked_lines = payslip.worked_days_line_ids


                # Work entry types
                work_type_normal = _get_or_create('WORK100', 'Attendance')
                work_type_half = _get_or_create('HALF', 'Half Day Attendance')
                work_type_unpaid = _get_or_create('LEAVE90', 'Unpaid (LOP)')
                work_type_casual = _get_or_create('CASUAL', 'Casual Leave (CL)')
                work_type_sick = _get_or_create('SICK', 'Sick Leave (SL)')
                work_type_earned = _get_or_create('EARNED', 'Earned Leave')
                work_type_public = _get_or_create('PUBHOL', 'Public Holiday')
                work_type_out = _get_or_create('OUT', 'Out of Contract')

   
            
                # Identify alt Saturdays (2nd & 4th)
                saturdays = [d for d in all_days if d.weekday() == 5]
                saturday_offs = []
                if len(saturdays) >= 2:
                    saturday_offs.append(saturdays[1])
                if len(saturdays) >= 4:
                    saturday_offs.append(saturdays[3])
            
                # Working days Mon–Sat except 2nd/4th Sat
                working_days = [d for d in all_days if (d.weekday() in (0,1,2,3,4,5) and d not in saturday_offs)]
                expected_working_days = len(working_days)
                total_working_days = expected_working_days
                payslip.total_working_days_in_month = expected_working_days
                
            
             
            
                full_days = 0
                half_days = 0
                paid_leave_days = 0
                unpaid_days = 0
                out_days = 0
            
                for line in worked_lines:
            
                    code = line.work_entry_type_id.code.upper() if line.work_entry_type_id else line.code.upper()
                    days = line.number_of_days or 0
            
                    # Attendance full day
                    if code in ('WORK100', 'ATTENDANCE'):
                        full_days += days
            
                    # Half day
                    elif code in ('HALF', 'HALFDAY'):
                        half_days += 0.5
            
                    # Paid leave (CL, SL, Earned, Public Holiday)
                    elif code in ('CASUAL', 'SICK', 'EARNED', 'PUBHOL', 'PAID', 'PL'):
                        paid_leave_days += days
            
                    # Unpaid / LOP
                    elif code in ('LEAVE90', 'UNPAID', 'LOP'):
                        unpaid_days += days
            
                    # Out-of-contract
                    elif code in ('OUT',):
                        out_days += days
                        
                for line in input_lines:
                    code = line.input_type_id.code.upper() if line.input_type_id else line.code.upper()
                    days = line.amount or 0

                    if code in ('LOP_RP'):
                        unpaid_days += days
            
            
                # Count total paid
                total_present = full_days + half_days   # half_days already numeric (0.5)
            
                counted_days = total_present + paid_leave_days + unpaid_days + out_days
            
                # 🔑 SINGLE SOURCE OF TRUTH → worked_days_line_ids
                paid_days = 0.0
                unpaid_days = 0.0
                
                for line in worked_lines:
                    code = line.work_entry_type_id.code.upper()
                
                    if code in ('WORK100', 'HALF', 'CASUAL', 'SICK', 'EARNED', 'PUBHOL'):
                        paid_days += line.number_of_days
                    elif code in ('LEAVE90', 'OUT'):
                        unpaid_days += line.number_of_days
                
                payslip.paid_days = paid_days
                payslip.unpaid_days = unpaid_days
                
                per_day_cost = contract.wage / total_working_days if total_working_days else 0
                payslip.paid_amount = paid_days * per_day_cost
                payslip.unpaid_amount = unpaid_days * per_day_cost



            
                continue


         
            # -------------------------------------------------------------------
            # CASE 2: If NOT calendar → CUSTOM attendance based payroll
            # -------------------------------------------------------------------
            
            if contract.work_entry_source != 'calendar':
            
                calendar = contract.resource_calendar_id
                date_from = payslip.date_from
                date_to = payslip.date_to
            
                payslip.worked_days_line_ids.unlink()
            
                # -------------------------------------------------------
                # 1️⃣ Get WORKING DAYS dynamically from calendar
                # -------------------------------------------------------
                def _is_working_day(cal, day):
                    start = datetime.combine(day, time.min)
                    end = datetime.combine(day, time.max)
                    return cal.get_work_hours_count(start, end) > 0
            
                working_days = []
                cur = date_from
                while cur <= date_to:
                    if _is_working_day(calendar, cur):
                        working_days.append(cur)
                    cur += timedelta(days=1)
            
                expected_working_days = len(working_days)
                payslip.total_working_days_in_month = expected_working_days
            
                # -------------------------------------------------------
                # 2️⃣ Fetch APPROVED LEAVES (DAY-WISE, NO DOUBLE COUNT)
                # -------------------------------------------------------
                leave_dates_paid = set()
                leave_dates_unpaid = set()
            
                leaves = Leave.search([
                    ('employee_id', '=', employee.id),
                    ('state', 'in', ('validate', 'approved')),
                    ('request_date_from', '<=', date_to),
                    ('request_date_to', '>=', date_from),
                ])
            
                for lv in leaves:
                    cur = max(lv.request_date_from, date_from)
                    end = min(lv.request_date_to, date_to)
            
                    while cur <= end:
                        if cur in working_days:
                            if lv.holiday_status_id.unpaid:
                                leave_dates_unpaid.add(cur)
                            else:
                                leave_dates_paid.add(cur)
                        cur += timedelta(days=1)
            
                paid_leave_days = len(leave_dates_paid)
                unpaid_leave_days = len(leave_dates_unpaid)
            
                # -------------------------------------------------------
                # 3️⃣ Fetch ATTENDANCE (DAY-WISE)
                # -------------------------------------------------------
                attendances = Attendance.search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', datetime.combine(date_from, time.min)),
                    ('check_out', '<=', datetime.combine(date_to, time.max)),
                ])
            
                attendance_map = {}  # date → hours
            
                for att in attendances:
                    if not att.check_in or not att.check_out:
                        continue
            
                    work_date = att.check_in.date()
                    if work_date not in working_days:
                        continue
            
                    hours = (att.check_out - att.check_in).total_seconds() / 3600
                    attendance_map[work_date] = max(attendance_map.get(work_date, 0), hours)
            
                full_days = 0.0
                half_days = 0.0
            
                for d, hrs in attendance_map.items():
                    if hrs >= 7:
                        full_days += 1
                    elif hrs >= 3:
                        half_days += 0.5
            
                # -------------------------------------------------------
                # 4️⃣ OUT OF CONTRACT DAYS
                # -------------------------------------------------------
                out_days = [
                    d for d in working_days
                    if (contract.date_start and d < contract.date_start)
                    or (contract.date_end and d > contract.date_end)
                ] 
                out_day_count = len(out_days)
            
                # -------------------------------------------------------
                # 5️⃣ AUTO UNPAID DAYS (ABSENT)
                # -------------------------------------------------------
                unpaid_auto_days = 0.0

                for d in working_days:
                    if d in out_days:
                        continue
                    if d in leave_dates_paid or d in leave_dates_unpaid:
                        continue
                
                    if d not in attendance_map:
                        unpaid_auto_days += 1.0
                    else:
                        hrs = attendance_map[d]
                        if 3 <= hrs < 7:
                            unpaid_auto_days += 0.5   # 🔑 HALF DAY BALANCE
                # -------------------------------------------------------
                # 6️⃣ FINAL COUNTS (BALANCED)
                # -------------------------------------------------------
                paid_days = full_days + half_days + paid_leave_days
                unpaid_days = unpaid_leave_days + unpaid_auto_days + out_day_count
            
                payslip.paid_days = paid_days
                payslip.unpaid_days = unpaid_days
            
                # SAFETY CHECK
                if round(paid_days + unpaid_days, 2) != round(expected_working_days, 2):
                    _logger.warning(
                        "Payroll mismatch: Paid(%s) + Unpaid(%s) != Working(%s)",
                        paid_days, unpaid_days, expected_working_days
                    )
            
                # -------------------------------------------------------
                # 7️⃣ AMOUNT CALCULATION
                # -------------------------------------------------------
                per_day_cost = contract.wage / expected_working_days if expected_working_days else 0
            
                payslip.paid_amount = paid_days * per_day_cost
                payslip.unpaid_amount = unpaid_days * per_day_cost
            
                # -------------------------------------------------------
                # 8️⃣ WORKED DAYS LINES (UI)
                # -------------------------------------------------------
                worked_lines = []
            
                if full_days:
                    worked_lines.append({
                        'name': 'Attendance',
                        'code': 'WORK100',
                        'number_of_days': full_days,
                        'number_of_hours': full_days * 8,
                        'work_entry_type_id': _get_or_create('WORK100', 'Attendance').id,
                    })
            
                if half_days:
                    worked_lines.append({
                        'name': 'Half Day Attendance',
                        'code': 'HALF',
                        'number_of_days': half_days,
                        'number_of_hours': half_days * 8,
                        'work_entry_type_id': _get_or_create('HALF', 'Half Day Attendance').id,
                    })
            
                if unpaid_days:
                    worked_lines.append({
                        'name': 'Unpaid / LOP',
                        'code': 'LEAVE90',
                        'number_of_days': unpaid_days,
                        'number_of_hours': unpaid_days * 8,
                        'work_entry_type_id': _get_or_create('LEAVE90', 'Unpaid').id,
                    })
            
                payslip.worked_days_line_ids = [(0, 0, vals) for vals in worked_lines]



        return super(HrPayslip, self).compute_sheet()
