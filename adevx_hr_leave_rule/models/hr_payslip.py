# models/hr_payslip.py
from odoo import models, fields, api
from datetime import timedelta, time
import math
import calendar

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
                        half_days += days
            
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
            
                # Final unpaid calculation
                total_unpaid_days = unpaid_days
                payslip.unpaid_days = total_unpaid_days
            
                # Payroll calculation
                per_day_cost = contract.wage / total_working_days if total_working_days else 0
            
                payslip.unpaid_amount = total_unpaid_days * per_day_cost
                payslip.paid_amount = contract.wage - payslip.unpaid_amount
                payslip.paid_days = total_working_days - total_unpaid_days
            
                continue


            # -------------------------------------------------------------------
            # CASE 2: If NOT calendar → use your existing custom logic

            if contract.work_entry_source != 'calendar' :

                date_from = payslip.date_from
                date_to = payslip.date_to
                payslip.worked_days_line_ids.unlink()
    
                # --- Calculate total days in month ---
                month_days = calendar.monthrange(date_from.year, date_from.month)[1]
                payslip.total_days_in_month = month_days
    
                # Build all days in the period
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
                    entry_date = fields.Date.from_string(entry.date_start)
                    if entry_date in unwanted_saturdays:
                        entry.unlink()

                # Work entry types
                work_type_normal = _get_or_create('WORK100', 'Attendance')
                work_type_half = _get_or_create('HALF', 'Half Day Attendance')
                work_type_unpaid = _get_or_create('LEAVE90', 'Unpaid (LOP)')
                work_type_casual = _get_or_create('CASUAL', 'Casual Leave (CL)')
                work_type_sick = _get_or_create('SICK', 'Sick Leave (SL)')
                work_type_earned = _get_or_create('EARNED', 'Earned Leave')
                work_type_public = _get_or_create('PUBHOL', 'Public Holiday')
                work_type_out = _get_or_create('OUT', 'Out of Contract')
                
    
                # Identify 2nd & 4th Saturday offs
                saturdays = [d for d in all_days if d.weekday() == 5]
                saturday_offs = []
                if len(saturdays) >= 2:
                    saturday_offs.append(saturdays[1])
                if len(saturdays) >= 4:
                    saturday_offs.append(saturdays[3])
    
                # Working days: Mon–Sat except 2nd & 4th Sat
                working_days = [d for d in all_days if (d.weekday() in (0,1,2,3,4,5) and d not in saturday_offs)]
                expected_working_days = len(working_days)
                payslip.total_working_days_in_month = expected_working_days
    
                # Department-specific Saturday working hours
                dept = (employee.department_id.name or '').upper()
                sat_hours_required = 4.0 if 'SGNA' in dept else 8.0
    
                # Get approved leaves
                leaves = Leave.search([
                    ('employee_id', '=', employee.id),
                    ('state', 'in', ('validate', 'approved')),
                    ('request_date_from', '<=', date_to),
                    ('request_date_to', '>=', date_from),
                ])
    
                leaves_summary = {}
                leave_dates = set()
                paid_leave_days = 0.0
                unpaid_leave_days = 0.0
    
                for lv in leaves:
                    days = lv.number_of_days if hasattr(lv, 'number_of_days') else 0
                    lt = (lv.holiday_status_id.name or 'Other').upper()
                    leaves_summary.setdefault(lt, 0.0)
                    leaves_summary[lt] += days
                    start = lv.request_date_from
                    end = lv.request_date_to
                    current = start
                    while current <= end:
                        leave_dates.add(current)
                        current += timedelta(days=1)
                    if 'UNPAID' in lt or 'LOP' in lt:
                        unpaid_leave_days += days
                    else:
                        paid_leave_days += days
    
                # Attendance
                attendances = Attendance.search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', date_from),
                    ('check_out', '<=', date_to),
                ])
    
                full_days = 0.0
                half_days = 0.0
                attended_dates = set()
    
                for att in attendances:
                    if not att.check_in or not att.check_out:
                        continue
                    duration = (att.check_out - att.check_in).total_seconds() / 3600.0
                    work_date = att.check_in.date()
                    attended_dates.add(work_date)
                    is_sat = (att.check_in.weekday() == 5)
                    if is_sat:
                        if duration >= sat_hours_required - 1:
                            full_days += 1
                        elif duration >= 3:
                            half_days += 1
                    else:
                        if duration >= 7:
                            full_days += 1
                        elif duration >= 3:
                            half_days += 1
    
                # Out of Contract
                contract_start = contract.date_start
                contract_end = contract.date_end
                out_days = [
                    d for d in working_days
                    if (contract_start and d < contract_start) or (contract_end and d > contract_end)
                ]
                out_day_count = len(out_days)
    
                # Unpaid days (no attendance + no leave)
                unpaid_dates = [
                    d for d in working_days
                    if (d not in attended_dates and d not in leave_dates and d not in out_days)
                ]
                unpaid_auto_days = len(unpaid_dates)
    
                total_present = full_days + (half_days * 0.5)
                total_leaves = paid_leave_days + unpaid_leave_days
                # counted_days = total_present + total_leaves + unpaid_auto_days + out_day_count
                # lop_days = max(expected_working_days - counted_days, 0)
    
    
                counted_days = total_present + total_leaves + unpaid_auto_days + out_day_count
                lop_days = max(expected_working_days - counted_days, 0)
                
                # FIX: Remove out_day_count from total_unpaid_days
                total_unpaid_days = unpaid_leave_days + unpaid_auto_days + lop_days
                payslip.unpaid_days = total_unpaid_days
                
                # total_unpaid_days = unpaid_leave_days + unpaid_auto_days + lop_days + out_day_count
                # payslip.unpaid_days = total_unpaid_days
    
                # Cost
                per_day_cost = contract.wage / expected_working_days if expected_working_days else 0
                half_day_cost = per_day_cost / 2
    
                # Build worked day lines
                worked_lines = []
    
                # Attendance
                if full_days:
                    worked_lines.append({
                        'name': 'Attendance',
                        'sequence': 1,
                        'code': 'WORK100',
                        'number_of_days': full_days,
                        'number_of_hours': full_days * 8,
                        'version_id': contract.id,
                        'work_entry_type_id': work_type_normal.id,
                        'amount': per_day_cost * full_days,
                    })
    
                # Half day
                if half_days:
                    worked_lines.append({
                        'name': 'Half Day Attendance',
                        'sequence': 2,
                        'code': 'HALF',
                        'number_of_days': half_days * 0.5,
                        'number_of_hours': half_days * 4,
                        'version_id': contract.id,
                        'work_entry_type_id': work_type_half.id,
                        'amount': half_days * half_day_cost,
                    })
    
                # Leaves
                for lt, days in leaves_summary.items():
                    if 'CASUAL' in lt:
                        wentry = work_type_casual
                    elif 'SICK' in lt:
                        wentry = work_type_sick
                    elif 'EARNED' in lt:
                        wentry = work_type_earned
                    elif 'PUBLIC' in lt:
                        wentry = work_type_public
                    elif 'UNPAID' in lt or 'LOP' in lt:
                        wentry = work_type_unpaid
                    else:
                        wentry = work_type_normal
                    worked_lines.append({
                        'name': f'{lt.title()} (Leave)',
                        'sequence': 3,
                        'code': lt[:8].upper(),
                        'number_of_days': days,
                        'number_of_hours': days * 8,
                        'version_id': contract.id,
                        'work_entry_type_id': wentry.id,
                        'amount': days * per_day_cost,
                    })
    
                # Unpaid / LOP
                if total_unpaid_days:
                    worked_lines.append({
                        'name': 'Unpaid / LOP Days',
                        'sequence': 4,
                        'code': 'LEAVE90',
                        'number_of_days': total_unpaid_days,
                        'number_of_hours': total_unpaid_days * 8,
                        'version_id': contract.id,
                        'work_entry_type_id': work_type_unpaid.id,
                        'amount': total_unpaid_days * per_day_cost,
                    })
    
                # Out of Contract
                if out_day_count:
                    worked_lines.append({
                        'name': 'Out of Contract',
                        'sequence': 5,
                        'code': 'OUT',
                        'number_of_days': out_day_count,
                        'number_of_hours': out_day_count * 8,
                        'version_id': contract.id,
                        'work_entry_type_id': work_type_out.id,
                        'amount': out_day_count * per_day_cost,
                    })
    
                # Assign to payslip
                payslip.worked_days_line_ids = [(0, 0, vals) for vals in worked_lines]
    
                # Calculate unpaid & paid amounts
                unpaid_total = 0.0
                for line in worked_lines:
                    if line['code'] in ('OUT', 'LEAVE90'):
                        unpaid_total += line['amount']
    
                payslip.unpaid_amount = unpaid_total
                payslip.paid_amount = (contract.wage or 0.0) - unpaid_total
                payslip.paid_days = expected_working_days - total_unpaid_days

        return super(HrPayslip, self).compute_sheet()
