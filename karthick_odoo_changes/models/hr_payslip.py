from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import timedelta, date

import calendar


class HrContract(models.Model):
    _inherit = 'hr.contract'

    is_normal_ot = fields.Boolean(string="Normal OT Eligible")
    is_friday_ot = fields.Boolean(string="Friday OT Eligible")

    # Percentages
    x_studio_basic_percent = fields.Float(string="Basic %", store=True)
    x_studio_tra_percent = fields.Float(string="Transport %", store=True)
    x_studio_hra_percent = fields.Float(string="HRA %", store=True)
    x_studio_fda_percent = fields.Float(string="FDA %", store=True)
    x_studio_tla_percent = fields.Float(string="TLA %", store=True)

    # Amounts
    x_studio_basic_salary = fields.Float(string="Basic Salary", store=True)
    x_studio_tra = fields.Float(string="Transport Allowance", store=True)
    x_studio_hra = fields.Float(string="House Rent Allowance", store=True)
    x_studio_fda = fields.Float(string="Food Allowance", store=True)
    x_studio_tla = fields.Float(string="Ticket Allowance", store=True)

    # -----------------------------
    # When amounts are changed
    # -----------------------------
    @api.onchange('x_studio_basic_salary', 'x_studio_tra', 'x_studio_hra', 'x_studio_fda', 'x_studio_tla')
    def _onchange_amounts_update_percentages(self):
        """Recalculate % fields when amount fields are changed"""
        for contract in self:
            wage = contract.wage or 0.0
            if wage <= 0:
                continue

            # Validate individual amounts not exceeding wage
            for field_name, label in [
                ('x_studio_basic_salary', 'Basic Salary'),
                ('x_studio_tra', 'Transport Allowance'),
                ('x_studio_hra', 'HRA'),
                ('x_studio_fda', 'Food Allowance'),
                ('x_studio_tla', 'Ticket Allowance'),
            ]:
                if getattr(contract, field_name) > wage:
                    setattr(contract, field_name, 0.0)
                    raise UserError(f"{label} cannot exceed contract wage.")

            # Compute percentages
            contract.x_studio_basic_percent = (contract.x_studio_basic_salary / wage) * 100
            contract.x_studio_tra_percent = (contract.x_studio_tra / wage) * 100
            contract.x_studio_hra_percent = (contract.x_studio_hra / wage) * 100
            contract.x_studio_fda_percent = (contract.x_studio_fda / wage) * 100
            contract.x_studio_tla_percent = (contract.x_studio_tla / wage) * 100

            # Validate total percentage
            total_percent = (
                contract.x_studio_basic_percent
                + contract.x_studio_tra_percent
                + contract.x_studio_hra_percent
                + contract.x_studio_fda_percent
                + contract.x_studio_tla_percent
            )
            if total_percent > 100:
                raise UserError("Total percentage (Basic + Transport + HRA + FDA + TLA) cannot exceed 100% of wage.")

    # -----------------------------
    # When percentages are changed
    # -----------------------------
    @api.onchange('x_studio_basic_percent', 'x_studio_tra_percent', 'x_studio_hra_percent', 'x_studio_fda_percent', 'x_studio_tla_percent')
    def _onchange_percentages_update_amounts(self):
        """Recalculate amount fields when % fields are changed"""
        for contract in self:
            wage = contract.wage or 0.0
            if wage <= 0:
                continue

            total_percent = (
                contract.x_studio_basic_percent
                + contract.x_studio_tra_percent
                + contract.x_studio_hra_percent
                + contract.x_studio_fda_percent
                + contract.x_studio_tla_percent
            )
            if total_percent > 100:
                raise UserError("Total percentage (Basic + Transport + HRA + FDA + TLA) cannot exceed 100% of wage.")

            # Compute amounts
            contract.x_studio_basic_salary = wage * contract.x_studio_basic_percent / 100.0
            contract.x_studio_tra = wage * contract.x_studio_tra_percent / 100.0
            contract.x_studio_hra = wage * contract.x_studio_hra_percent / 100.0
            contract.x_studio_fda = wage * contract.x_studio_fda_percent / 100.0
            contract.x_studio_tla = wage * contract.x_studio_tla_percent / 100.0





class HrPayslip(models.Model):
    _inherit = 'hr.payslip'



    # def compute_sheet(self):
    #     payslips = self.filtered(lambda slip: slip.state in ['draft', 'verify'])
    #     payslips.line_ids.unlink()
    #     payslips.worked_days_line_ids.unlink()
    #     self.env.flush_all()

    #     today = fields.Date.today()

    #     for payslip in payslips:
    #         employee = payslip.employee_id
    #         contract = payslip.contract_id
    #         if not contract:
    #             raise UserError(f"No contract found for {employee.name}.")

    #         wage = contract.wage or 0.0
    #         date_from = payslip.date_from
    #         date_to = payslip.date_to
    #         total_days = calendar.monthrange(date_from.year, date_from.month)[1]

    #         # per day and per hour wage
    #         per_day = wage / total_days
    #         per_hour = per_day / 8.0

    #         # collect attendance/work entry data
    #         work_entries = self.env['hr.work.entry'].search([
    #             ('employee_id', '=', employee.id),
    #             ('date_start', '>=', date_from),
    #             ('date_stop', '<=', date_to),
    #         ])

    #         normal_work_days = len(set(w.date_start.date() for w in work_entries if w.work_entry_type_id.code == 'WORK100'))
    #         normal_ot_hours = sum(w.duration for w in work_entries if w.work_entry_type_id.code == 'NOR_OT')
    #         friday_ot_hours = sum(w.duration for w in work_entries if w.work_entry_type_id.code == 'FRI_OT')

    #         unpaid_days = total_days - normal_work_days

    #         # amounts
    #         unpaid_amount = per_day * unpaid_days
    #         normal_ot_amount = normal_ot_hours * (per_hour * 1.25) if contract.is_normal_ot else 0.0
    #         friday_ot_amount = friday_ot_hours * (per_hour * 1.5) if contract.is_friday_ot else 0.0


    #         # Fetch work entry types
    #         work_type_normal = self.env['hr.work.entry.type'].search([('code', '=', 'WORK100')], limit=1)
    #         work_type_unpaid = self.env['hr.work.entry.type'].search([('code', '=', 'UNPAID')], limit=1)
    #         work_type_nor_ot = self.env['hr.work.entry.type'].search([('code', '=', 'NOR_OT')], limit=1)
    #         work_type_fri_ot = self.env['hr.work.entry.type'].search([('code', '=', 'FRI_OT')], limit=1)
            
    #         worked_lines = []
            
    #         # Normal working days
    #         if normal_work_days > 0 and work_type_normal:
    #             worked_lines.append((0, 0, {
    #                 'name': 'Normal Working Days',
    #                 'code': 'WORK100',
    #                 'number_of_days': normal_work_days,
    #                 'number_of_hours': normal_work_days * 8,
    #                 'amount': per_day * normal_work_days,
    #                 'contract_id': contract.id,
    #                 'work_entry_type_id': work_type_normal.id,
    #             }))
            
    #         # Unpaid days
    #         if unpaid_days > 0 and work_type_unpaid:
    #             worked_lines.append((0, 0, {
    #                 'name': 'Unpaid Days',
    #                 'code': 'UNPAID',
    #                 'number_of_days': unpaid_days,
    #                 'number_of_hours': unpaid_days * 8,
    #                 'amount': -unpaid_amount,
    #                 'contract_id': contract.id,
    #                 'work_entry_type_id': work_type_unpaid.id,
    #             }))
            
    #         # Normal OT
    #         if normal_ot_hours > 0 and contract.is_normal_ot and work_type_nor_ot:
    #             worked_lines.append((0, 0, {
    #                 'name': 'Normal OT',
    #                 'code': 'NOR_OT',
    #                 'number_of_days': 0,
    #                 'number_of_hours': normal_ot_hours,
    #                 'amount': normal_ot_amount,
    #                 'contract_id': contract.id,
    #                 'work_entry_type_id': work_type_nor_ot.id,
    #             }))
            
    #         # Friday OT
    #         if friday_ot_hours > 0 and contract.is_friday_ot and work_type_fri_ot:
    #             worked_lines.append((0, 0, {
    #                 'name': 'Friday OT',
    #                 'code': 'FRI_OT',
    #                 'number_of_days': 0,
    #                 'number_of_hours': friday_ot_hours,
    #                 'amount': friday_ot_amount,
    #                 'contract_id': contract.id,
    #                 'work_entry_type_id': work_type_fri_ot.id,
    #             }))

    #         # write worked days
    #         payslip.write({
    #             'worked_days_line_ids': [(5, 0, 0)] + worked_lines,
    #             'state': 'verify',
    #             'compute_date': today,
    #         })

    #     # ✅ After attendance-based worked days — call Odoo’s default salary rule engine
    #     self.env['hr.payslip.line'].create(payslips._get_payslip_lines())

    #     # optional: handle YTD logic
    #     if any(payslips.mapped('ytd_computation')):
    #         self._compute_worked_days_ytd()

    #     return True


    def compute_sheet(self):
        WorkEntryType = self.env['hr.work.entry.type']
        AttendanceReport = self.env['hr.attendance']

        def _get_or_create(code, name):
            rec = WorkEntryType.search([('code', '=', code)], limit=1)
            if not rec:
                rec = WorkEntryType.create({'name': name, 'code': code})
            return rec

        # Work entry types
        work_type_normal = _get_or_create('WORK100', 'Normal Working Days')
        work_type_nor_ot = _get_or_create('NOR_OT', 'Normal OT Hours')
        work_type_fri_ot = _get_or_create('FRI_OT', 'Friday OT Hours')
        work_type_unpaid = _get_or_create('UNPAID', 'Unpaid Days')

        for payslip in self:
            contract = payslip.contract_id
            employee = contract.employee_id
            date_from = payslip.date_from
            date_to = payslip.date_to

            # Remove old worked days lines
            payslip.worked_days_line_ids.unlink()

            attendances = AttendanceReport.search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', date_from),
                ('check_out', '<=', date_to),
            ])

            total_days = (fields.Date.from_string(date_to) - fields.Date.from_string(date_from)).days + 1

            normal_days = set()
            normal_ot_hours = 0.0
            friday_ot_hours = 0.0

            no_of_fri = 0

            for att in attendances:
                if not att.check_in or not att.check_out:
                    continue
                day_hours = (att.check_out - att.check_in).total_seconds() / 3600.0
                weekday = att.check_in.weekday()  # Monday=0, Sunday=6

                if weekday == 4:  # Friday
                    friday_ot_hours += day_hours
                    no_of_fri += 1
                else:
                    normal_hours = min(day_hours, 8)
                    ot_hours = max(day_hours - 8, 0)
                    if normal_hours > 0:
                        normal_days.add(att.check_in.date())
                    normal_ot_hours += ot_hours

            all_days = []
            current_day = fields.Date.from_string(date_from)
            end_day = fields.Date.from_string(date_to)
            
            while current_day <= end_day:
                if current_day.weekday() != 4:  # Exclude Friday
                    all_days.append(current_day)
                current_day += timedelta(days=1)
            
            # Set of days employee actually worked (any attendance)
            worked_days = set(att.check_in.date() for att in attendances if att.check_in and att.check_out)
            
            # Unpaid days = working days without any attendance
            unpaid_days = len([d for d in all_days if d not in worked_days])

            per_day_cost = (contract.wage / len(all_days))  # Normal working day cost
            per_hour_cost = per_day_cost / 8  # Assuming 8 hours/day
            
            normal_ot_amount = normal_ot_hours * per_hour_cost * 1.25


            friday_ot_amount = friday_ot_hours * per_hour_cost * 1.5
            
            # For Unpaid
            unpaid_amount = (contract.wage / len(all_days)) * unpaid_days
            # For Normal Days
            normal_amount = (contract.wage / len(all_days)) * len(normal_days)

            worked_lines = []

            if normal_days:
                worked_lines.append({
                    'name': 'Normal Working Days',
                    'sequence': 1,
                    'code': 'WORK100',
                    'number_of_days': len(normal_days),
                    'number_of_hours': len(normal_days) * 8,
                    'contract_id': contract.id,
                    'work_entry_type_id': work_type_normal.id,
                    'amount':normal_amount
                })
            if normal_ot_hours and getattr(contract, 'is_normal_ot', False):
                worked_lines.append({
                    'name': 'Normal OT Hours',
                    'sequence': 2,
                    'code': 'NOR_OT',
                    'number_of_days': 0,
                    'number_of_hours': normal_ot_hours,
                    'contract_id': contract.id,
                    'work_entry_type_id': work_type_nor_ot.id,
                      'amount':normal_ot_amount
                })
            if friday_ot_hours and getattr(contract, 'is_friday_ot', False):
                worked_lines.append({
                    'name': 'Friday OT Hours',
                    'sequence': 3,
                    'code': 'FRI_OT',
                    'number_of_days': no_of_fri,
                    'number_of_hours': friday_ot_hours,
                    'contract_id': contract.id,
                    'work_entry_type_id': work_type_fri_ot.id,
                     'amount':friday_ot_amount
                })
            if unpaid_days > 0:
                worked_lines.append({
                    'name': 'Absent days',
                    'sequence': 4,
                    'code': 'UNPAID',
                    'number_of_days': unpaid_days,
                    'number_of_hours': unpaid_days * 8,
                    'contract_id': contract.id,
                    'work_entry_type_id': work_type_unpaid.id,
                     'amount':unpaid_amount
                })

            payslip.worked_days_line_ids = [(0, 0, vals) for vals in worked_lines]
             

       
        return super(HrPayslip, self).compute_sheet()



class HrWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    @api.depends('is_paid', 'is_credit_time', 'number_of_hours', 'payslip_id', 'contract_id.wage', 'payslip_id.sum_worked_hours')
    def _compute_amount(self):
        for worked_days in self:
            # Skip if edited or payslip not in draft/verify
            if worked_days.payslip_id.edited or worked_days.payslip_id.state not in ['draft', 'verify']:
                continue

            # Skip for OUT or credit time
            if not worked_days.contract_id or worked_days.code == 'OUT' or worked_days.is_credit_time:
                worked_days.amount = 0
                continue

            contract = worked_days.contract_id
            payslip = worked_days.payslip_id

            # Calculate total working days (excluding Fridays)
            date_from = payslip.date_from
            date_to = payslip.date_to
            all_days = []
            current_day = fields.Date.from_string(date_from)
            end_day = fields.Date.from_string(date_to)
            while current_day <= end_day:
                if current_day.weekday() != 4:  # exclude Friday
                    all_days.append(current_day)
                current_day += timedelta(days=1)

            per_day_cost = (contract.wage / len(all_days)) if len(all_days) else 0
            per_hour_cost = per_day_cost / 8

            # Compute amount based on worked_days code
            if worked_days.code == 'WORK100':  # Normal days
                worked_days.amount = per_day_cost * worked_days.number_of_days if worked_days.is_paid else 0
            elif worked_days.code == 'UNPAID':
                worked_days.amount = per_day_cost * worked_days.number_of_days if worked_days.is_paid else 0
            elif worked_days.code == 'NOR_OT':
                worked_days.amount = per_hour_cost * 1.25 * worked_days.number_of_hours if worked_days.is_paid else 0
            elif worked_days.code == 'FRI_OT':
                worked_days.amount = per_hour_cost * 1.5 * worked_days.number_of_hours if worked_days.is_paid else 0
            else:
                # fallback to original logic
                if payslip.wage_type == "hourly":
                    worked_days.amount = contract.hourly_wage * worked_days.number_of_hours if worked_days.is_paid else 0
                else:
                    worked_days.amount = contract.contract_wage * worked_days.number_of_hours / (payslip._get_regular_worked_hours() or 1) if worked_days.is_paid else 0


