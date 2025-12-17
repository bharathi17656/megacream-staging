from datetime import datetime, timedelta, time
import pytz
import logging
from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)



class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    x_is_half_day = fields.Boolean(string="Half Day", default=False)
    x_is_full_day = fields.Boolean(string="Full Day", default=False)




class LateEntry(models.Model):
    _name = 'attendance_advance.late_entry'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    
    _description = 'Late Entry and appeal record'
    _order = 'date desc'
  

    name = fields.Char(string="Name", compute="_compute_name", store=True)

    @api.depends('employee_id', 'date')
    def _compute_name(self):
        for rec in self:
            if rec.employee_id and rec.date:
                rec.name = f"Late Entry - {rec.employee_id.name} - {rec.date.strftime('%d %b %Y')}"
            else:
                rec.name = "Late Entry"



    can_request = fields.Boolean(string="Can Request", compute="_compute_access_flags")
    can_approve = fields.Boolean(string="Can Approve", compute="_compute_access_flags")
    can_reject = fields.Boolean(string="Can Reject", compute="_compute_access_flags")


    def _compute_access_flags(self):
        """Compute button visibility logic dynamically per user."""
        for rec in self:
            user = self.env.user
            rec.can_request = False
            rec.can_approve = False
            rec.can_reject = False
    
            # --- Admin always has full access ---
            if user.has_group('base.group_system'):
                rec.can_request = True
                rec.can_approve = True
                rec.can_reject = True
                continue
    
            # --- Employee can request only their own record ---
            if rec.employee_id.user_id.id == user.id and rec.status == 'draft':
                rec.can_request = True
    
            # --- Approvers: get from approval config ---
            config = self.env['attendance_advance.approval_config'].search([
                ('request_department_id', '=', rec.employee_id.department_id.id)
            ], limit=1)
            if config and config.approver_employee_ids:
                if rec.status == 'requested':
                    approver_users = config.approver_employee_ids.mapped('user_id.id')
                    if user.id in approver_users:
                        rec.can_approve = True
                        rec.can_reject = True
    

    employee_id = fields.Many2one('hr.employee', required=True)
    attendance_id = fields.Many2one('hr.attendance', string="Related Attendance", ondelete='set null')
    date = fields.Date(required=True)
   
    minutes_late_in = fields.Float(string="Late Minutes (In)", default=0.0)
    minutes_early_out = fields.Float(string="Early Minutes (Out)", default=0.0)
    total_violation_minutes = fields.Float(string="Total Violation (Minutes)", compute="_compute_total_violation", store=True)

    @api.depends('minutes_late_in', 'minutes_early_out')
    def _compute_total_violation(self):
        for rec in self:
            rec.total_violation_minutes = (rec.minutes_late_in or 0.0) + (rec.minutes_early_out or 0.0)

    
    half_pay = fields.Boolean(default=False)
    full_day = fields.Boolean(default=False)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], default='draft')
    appeal_reason = fields.Text()
    approved_by = fields.Many2one('hr.employee')
    approval_date = fields.Datetime()

    # ------------------------
    # CRON PROCESS
    # ------------------------
    # @api.model
    # def _cron_process_attendances(self):
    #     """Daily cron to detect late arrivals and create Late Entry records (timezone-safe)."""
    #     today = fields.Date.today()
    #     Attendance = self.env['hr.attendance']
    #     WorkSchedule = self.env['attendance_advance.work_schedule']

    #     user_tz = pytz.timezone(self.env.user.tz or 'UTC')
    #     start_local = datetime.combine(today, datetime.min.time())
    #     end_local = datetime.combine(today, datetime.max.time())
    #     start_utc = user_tz.localize(start_local).astimezone(pytz.UTC).replace(tzinfo=None)
    #     end_utc = user_tz.localize(end_local).astimezone(pytz.UTC).replace(tzinfo=None)

    #     attendances = Attendance.search([
    #         ('check_in', '>=', start_utc),
    #         ('check_in', '<=', end_utc)
    #     ])

    #     _logger.info("Late Entry Cron Started — Found %s attendance records", len(attendances))

    #     for att in attendances:
    #         employee = att.employee_id
    #         if not employee:
    #             continue

    #         schedule = WorkSchedule.search([
    #             '|',
    #             ('employee_ids', 'in', employee.id),
    #             ('department_id', '=', employee.department_id.id)
    #         ], limit=1)

    #         if not schedule:
    #             continue

    #         weekday = str((att.check_in.weekday() + 1) % 7)
    #         line = schedule.schedule_line_ids.filtered(lambda l: l.day == weekday)
    #         if not line:
    #             continue

    #         start_time = line.start_time or 0.0
    #         grace = schedule.grace_in_minutes or 0

    #         local_start = datetime.combine(att.check_in.date(), time(int(start_time), int((start_time % 1) * 60)))
    #         local_start_dt = user_tz.localize(local_start).astimezone(pytz.UTC).replace(tzinfo=None)
    #         allowed_latest = local_start_dt + timedelta(minutes=grace)

    #         if att.check_in > allowed_latest:
    #             late_minutes = (att.check_in - allowed_latest).total_seconds() / 60.0

    #             existing = self.search([
    #                 ('employee_id', '=', employee.id),
    #                 ('attendance_id', '=', att.id)
    #             ], limit=1)
    #             if existing:
    #                 continue

    #             self.create({
    #                 'employee_id': employee.id,
    #                 'attendance_id': att.id,
    #                 'date': today,
    #                 'minutes_late': round(late_minutes, 1),
    #                 'status': 'draft',
    #                 'half_pay': False,
    #                 'full_day': False,
    #             })
    #             _logger.info("Late Entry Created: %s - %.1f mins late", employee.name, late_minutes)

    #     _logger.info("Late Entry Cron Finished.")
    #     return True


    @api.model
    def _cron_process_attendances(self):
        """Daily cron — detect late-ins or early-outs strictly based on Advance Schedule (per department/employee)."""
        today = fields.Date.today()
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
    
        Attendance = self.env['hr.attendance']
        WorkSchedule = self.env['attendance_advance.work_schedule']
    
        # fetch all schedules
        schedules = WorkSchedule.search([])
        _logger.info("Late Entry Cron Started — Processing %s work schedules", len(schedules))
        month_start = today.replace(day=1)
        month_start_dt = datetime.combine(month_start, datetime.min.time())
        today_end_dt = datetime.combine(today, datetime.max.time())

        for schedule in schedules:
            grace_in = schedule.grace_in_minutes or 0
            grace_out = schedule.grace_out_minutes or 0

            
            for emp in schedule.employee_ids:
                # find today's attendance for that employee (excluding full/half day)
                att = Attendance.search([
                    ('employee_id', '=', emp.id),
                    ('check_in', '>=', datetime.combine(today, datetime.min.time())),
                    ('check_in', '<=', datetime.combine(today, datetime.max.time())),
                    ('x_is_full_day', '=', False),
                    ('x_is_half_day', '=', False),
                ], limit=1)

                               
                _logger.info("Late Entry Cron Started — Processing %s work schedules first")
                if not att:
                    continue
    
                weekday_name = att.check_in.strftime('%A')  # e.g., "Monday"
                line = schedule.schedule_line_ids.filtered(lambda l: l.day.lower() == weekday_name.lower())
                if not line:
                    continue
                _logger.info("Late Entry Cron Started — Processing %s work schedules second")
                line = line[0]
    
                # --- Handle alternate Saturday ---
                if weekday_name.lower() == 'saturday' and line.pattern_type in ('alternate', 'custom'):
                    week_num = (att.check_in.day - 1) // 7 + 1
                    if line.pattern_type == 'alternate' and week_num not in (1, 3):
                        _logger.info("Skipping non-working Saturday (%s) for %s", week_num, emp.name)
                        continue
    
                # --- Compute scheduled boundaries ---
                start_time = line.start_time or 0.0
                end_time = line.end_time or 0.0
    
                start_dt = datetime.combine(att.check_in.date(), time(int(start_time), int((start_time % 1) * 60)))
                end_dt = datetime.combine(att.check_in.date(), time(int(end_time), int((end_time % 1) * 60)))
    
                allowed_in = start_dt + timedelta(minutes=grace_in)
                allowed_out = end_dt - timedelta(minutes=grace_out)
    
                minutes_late_in = 0.0
                minutes_early_out = 0.0
    
                # --- Late In ---
                if att.check_in > allowed_in:
                    minutes_late_in = (att.check_in - allowed_in).total_seconds() / 60.0
    
                # --- Early Out ---
                if att.check_out and att.check_out < allowed_out:
                    minutes_early_out = (allowed_out - att.check_out).total_seconds() / 60.0
    
                if minutes_late_in <= 0 and minutes_early_out <= 0:
                    continue  # no violation
    
                # --- Create or update Late Entry ---
                existing = self.search([
                    ('employee_id', '=', emp.id),
                    ('attendance_id', '=', att.id)
                ], limit=1)
    
                vals = {
                    'employee_id': emp.id,
                    'attendance_id': att.id,
                    'date': today,
                    'minutes_late_in': round(minutes_late_in, 1),
                    'minutes_early_out': round(minutes_early_out, 1),
                    'status': 'draft',
                    'half_pay': False,
                    'full_day': False,
                }
    
                if existing:
                    existing.write(vals)
                    _logger.info("Updated Late Entry for %s — In: %.1f min, Out: %.1f min", emp.name, minutes_late_in, minutes_early_out)
                else:
                    self.create(vals)
                    _logger.info("Created Late Entry for %s — In: %.1f min, Out: %.1f min", emp.name, minutes_late_in, minutes_early_out)
    
        _logger.info("Late Entry Cron Finished.")
        return True



    @api.model
    def _cron_process_attendances_months(self):
        """Detect Late-Ins and Early-Outs from start of month till today based on Work Schedule."""
        today = fields.Date.today()
        month_start = today.replace(day=1)

        Attendance = self.env['hr.attendance']
        WorkSchedule = self.env['attendance_advance.work_schedule']

        # Determine timezone
        user_tz = pytz.timezone(self.env.user.tz or 'Asia/Kolkata')

        _logger.info("🔁 Late/Early Attendance Cron Started — Checking %s to %s", month_start, today)

        # Fetch all work schedules
        schedules = WorkSchedule.search([])
        for schedule in schedules:
            grace_in = schedule.grace_in_minutes or 0
            grace_out = schedule.grace_out_minutes or 0

            for emp in schedule.employee_ids:
                # Get attendance records from start of month till today
                month_start_dt = datetime.combine(month_start, datetime.min.time())
                today_end_dt = datetime.combine(today, datetime.max.time())

                attendances = Attendance.search([
                    ('employee_id', '=', emp.id),
                    ('check_in', '>=', month_start_dt),
                    ('check_in', '<=', today_end_dt),
                    ('x_is_full_day', '=', False),
                    ('x_is_half_day', '=', False),
                ])

                if not attendances:
                    continue
                _logger.info("Late Entry Cron Started — Processing %s work schedules second")

                for att in attendances:
                    # Convert to local timezone to determine actual working day
                    local_dt = pytz.UTC.localize(att.check_in).astimezone(user_tz)
                    weekday_name = local_dt.strftime('%A')  # e.g. 'Monday'
                    weekday_num = int(att.check_in.weekday()) + 1
                    weekday_num = str(weekday_num)
                    
                    # Find schedule line for the weekday
                    line = schedule.schedule_line_ids.filtered(lambda l: l.day == weekday_num )
                    _logger.info("Late Entry Cron Started — Processing %s %s work schedules third",line,weekday_num)
                    if not line:
                        continue
                    _logger.info("Late Entry Cron Started — Processing %s work schedules third")
                    line = line[0]

                    # --- Handle Alternate Saturday Logic ---
                    if weekday_name.lower() == 'saturday' and line.pattern_type in ('alternate', 'custom'):
                        week_num = (local_dt.day - 1) // 7 + 1
                        if line.pattern_type == 'alternate' and week_num not in (1, 3 , 5):
                            _logger.info("🟡 Skipping non-working Saturday (Week %s) for %s", week_num, emp.name)
                            continue  # Skip 2nd, 4th, Saturdays

                    # Compute working hours based on schedule
                    start_time = line.start_time or 0.0
                    end_time = line.end_time or 0.0

                    # Compute schedule datetimes
                    start_dt_local = datetime.combine(att.check_in.date(), time(int(start_time), int((start_time % 1) * 60)))
                    end_dt_local = datetime.combine(att.check_in.date(), time(int(end_time), int((end_time % 1) * 60)))

                    # Convert schedule times to UTC for accurate comparison
                    start_dt_utc = user_tz.localize(start_dt_local).astimezone(pytz.UTC).replace(tzinfo=None)
                    end_dt_utc = user_tz.localize(end_dt_local).astimezone(pytz.UTC).replace(tzinfo=None)

                    # Apply grace periods
                    allowed_latest_in = start_dt_utc + timedelta(minutes=grace_in)
                    allowed_earliest_out = end_dt_utc - timedelta(minutes=grace_out)

                    minutes_late_in = 0.0
                    minutes_early_out = 0.0

                    # --- Late-In ---
                    if att.check_in > allowed_latest_in:
                        minutes_late_in = (att.check_in - allowed_latest_in).total_seconds() / 60.0

                    # --- Early-Out ---
                    if att.check_out and att.check_out < allowed_earliest_out:
                        minutes_early_out = (allowed_earliest_out - att.check_out).total_seconds() / 60.0

                    # Skip if no issue
                    if minutes_late_in <= 0 and minutes_early_out <= 0:
                        continue

                    _logger.info("Late Entry Cron Started — Processing %s work schedules fourth")
                    # --- Create or Update Late Entry Record ---
                    existing = self.search([
                        ('employee_id', '=', emp.id),
                        ('attendance_id', '=', att.id)
                    ], limit=1)

                    vals = {
                        'employee_id': emp.id,
                        'attendance_id': att.id,
                        'date': att.check_in.date(),
                        'minutes_late_in': round(minutes_late_in, 1),
                        'minutes_early_out': round(minutes_early_out, 1),
                        'status': 'draft',
                        'half_pay': False,
                        'full_day': False,
                    }

                    if existing:
                        existing.write(vals)
                        _logger.info("🔄 Updated Late/Early Entry: %s [%s] — Late In: %.1f min, Early Out: %.1f min",
                                     emp.name, att.check_in.date(), minutes_late_in, minutes_early_out)
                    else:
                        self.create(vals)
                        _logger.info("🆕 Created Late/Early Entry: %s [%s] — Late In: %.1f min, Early Out: %.1f min",
                                     emp.name, att.check_in.date(), minutes_late_in, minutes_early_out)

        _logger.info("✅ Late/Early Attendance Cron Finished.")
        return True

    
    # ------------------------
    # CONSTRAINT
    # ------------------------
    @api.constrains('minutes_late_in')
    def _check_minutes(self):
        for rec in self:
            if rec.minutes_late_in and rec.minutes_late_in < 0:
                raise ValidationError('Minutes Late In cannot be negative')
                
    @api.constrains('minutes_early_out')
    def _check_minutes(self):
        for rec in self:
            if rec.minutes_early_out and rec.minutes_early_out < 0:
                raise ValidationError('Minutes Early Out cannot be negative')

    # ------------------------
    # WORKFLOW ACTIONS
    # ------------------------
    def action_request_approval(self):
        self.ensure_one()
        if not self.can_request:
            raise ValidationError("You don't have permission to request approval for this record.")
        self.status = 'requested'
        self.message_post(body=f"{self.employee_id.name} requested approval for late entry on {self.date}.")
        self._send_approval_notification()




    def _send_approval_notification(self):
        """Send notification or activity to approvers or HR fallback."""
        self.ensure_one()
    
        config = self.env['attendance_advance.approval_config'].search([
            ('request_department_id', '=', self.employee_id.department_id.id)
        ], limit=1)
    
        notified_users = []
    
        # --- If department-level approvers are defined ---
        if config and config.approver_employee_ids:
            for approver in config.approver_employee_ids:
                if approver.user_id:
                    self.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=approver.user_id.id,
                        note=f"Please review late entry for {self.employee_id.name} ({self.date})"
                    )
                    notified_users.append(approver.user_id.name)
    
        # --- If no approver found, send to HR group ---
        else:
            hr_users = self.env.ref('hr.group_hr_user').users
            for u in hr_users:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=u.id,
                    note=f"Please review late entry for {self.employee_id.name} ({self.date})"
                )
                notified_users.append(u.name)
    
        # Log notification summary
        if notified_users:
            self.message_post(
                body=f"Approval request sent to: {', '.join(notified_users)}",
                subtype_xmlid="mail.mt_comment",
            )
        else:
            self.message_post(
                body="No approvers configured. HR notification skipped.",
                subtype_xmlid="mail.mt_comment",
            )

    
    def action_approve(self):
        self.ensure_one()
        if not self.can_approve:
            raise ValidationError("You don't have permission to approve this record.")
        self.status = 'approved'
        self.half_pay = False
        self.full_day = True
        self.approved_by = self.env.user.employee_ids and self.env.user.employee_ids[0].id or False
        self.approval_date = fields.Datetime.now()
        if self.attendance_id:
            self.attendance_id.write({'x_is_full_day': True, 'x_is_half_day': False})
    
    
    def action_reject(self):
        self.ensure_one()
        if not self.can_reject:
            raise ValidationError("You don't have permission to reject this record.")
        self.status = 'rejected'
        self.half_pay = True
        self.full_day = False
        self.approved_by = self.env.user.employee_ids and self.env.user.employee_ids[0].id or False
        self.approval_date = fields.Datetime.now()
        if self.attendance_id:
            self.attendance_id.write({'x_is_half_day': True, 'x_is_full_day': False})
    
    




















