import requests
from odoo import models, fields
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class BiotimeService(models.Model):
    _name = "biotime.service"
    _description = "Biotime API Service"

    # ------------------------------------------------
    # CONFIG
    # ------------------------------------------------
    def _get_config(self):
        ICP = self.env['ir.config_parameter'].sudo()
        base_url = ICP.get_param('biotime.base_url')
        username = ICP.get_param('biotime.username')
        password = ICP.get_param('biotime.password')

        if not base_url or not username or not password:
            raise UserError("Biotime credentials missing")
        _logger.warning("This is ______________________________ username %s password %s link %s",username,password,base_url)
        return base_url, username, password

    # ------------------------------------------------
    # FETCH TERMINALS
    # ------------------------------------------------
    def sync_terminals(self):
        base_url, username, password = self._get_config()
        url = f"{base_url}/iclock/api/terminals/"

        res = requests.get(url, auth=(username, password), timeout=30)
        res.raise_for_status()
        _logger.warning("This is ______________________________ record terminal %s",res)

        Terminal = self.env['biotime.terminal']

        for t in res.json().get("data", []):
            Terminal.search([
                ('biotime_id', '=', t['id'])
            ], limit=1).write({
                'sn': t.get('sn'),
                'ip_address': t.get('ip_address'),
                'alias': t.get('alias'),
                'terminal_name': t.get('terminal_name'),
                'fw_ver': t.get('fw_ver'),
                'push_ver': t.get('push_ver'),
                'state': t.get('state'),
                'terminal_tz': t.get('terminal_tz'),
                'last_activity': t.get('last_activity'),
                'user_count': t.get('user_count'),
                'fp_count': t.get('fp_count'),
                'face_count': t.get('face_count'),
                'palm_count': t.get('palm_count'),
                'transaction_count': t.get('transaction_count'),
                'push_time': t.get('push_time'),
                'transfer_time': t.get('transfer_time'),
                'transfer_interval': t.get('transfer_interval'),
                'is_attendance': t.get('is_attendance'),
                'area_name': t.get('area_name'),
                'company_uid': t.get('company'),
            }) or Terminal.create({'biotime_id': t['id'], **t})

    # ------------------------------------------------
    # FETCH BIODATA
    # ------------------------------------------------
    def sync_biodata(self):
        base_url, username, password = self._get_config()
        url = f"{base_url}/iclock/api/biodatas/"

        Biodata = self.env['biotime.biodata']
        Employee = self.env['hr.employee']

        while url:
            res = requests.get(url, auth=(username, password), timeout=30)
            res.raise_for_status()
            payload = res.json()

            for b in payload.get("data", []):
                emp_code = b['employee'].split()[0]

                employee = Employee.search([
                    ('biotime_emp_code', '=', emp_code)
                ], limit=1)

                Biodata.search([
                    ('biotime_id', '=', b['id'])
                ], limit=1).write({
                    'employee_name': b.get('employee'),
                    'emp_code': emp_code,
                    'bio_type': b.get('bio_type'),
                    'bio_no': b.get('bio_no'),
                    'bio_index': b.get('bio_index'),
                    'bio_tmp': b.get('bio_tmp'),
                    'major_ver': b.get('major_ver'),
                    'update_time': b.get('update_time'),
                    'employee_id': employee.id if employee else False,
                }) or Biodata.create({
                    'biotime_id': b['id'],
                    'employee_name': b.get('employee'),
                    'emp_code': emp_code,
                })

            url = payload.get("next")

    # ------------------------------------------------
    # FETCH TRANSACTIONS → ATTENDANCE
    # ------------------------------------------------
    def sync_attendance(self):
        base_url, username, password = self._get_config()
        url = f"{base_url}/iclock/api/transactions/"

        HrAttendance = self.env['hr.attendance']
        HrAttendanceLine = self.env['hr.attendance.line']
        Employee = self.env['hr.employee']

        grouped = {}

        while url:
            res = requests.get(url, auth=(username, password), timeout=30)
            res.raise_for_status()
            payload = res.json()

            for tx in payload.get("data", []):
                emp_code = tx.get('emp_code')
                employee = Employee.search([
                    ('biotime_emp_code', '=', emp_code)
                ], limit=1)

                if not employee:
                    continue

                punch_time = fields.Datetime.from_string(tx['punch_time'])
                date = punch_time.date()

                grouped.setdefault(
                    (employee.id, date),
                    []
                ).append(tx)

            url = payload.get("next")

        for (employee_id, date), punches in grouped.items():
            punches.sort(key=lambda x: x['punch_time'])

            attendance = HrAttendance.search([
                ('employee_id', '=', employee_id),
                ('check_in', '>=', f"{date} 00:00:00"),
                ('check_in', '<=', f"{date} 23:59:59"),
            ], limit=1)

            if not attendance:
                attendance = HrAttendance.create({
                    'employee_id': employee_id,
                    'check_in': punches[0]['punch_time'],
                    'check_out': punches[-1]['punch_time'],
                })
            else:
                attendance.write({
                    'check_out': punches[-1]['punch_time']
                })

            for tx in punches:
                HrAttendanceLine.create({
                    'attendance_id': attendance.id,
                    'employee_id': employee_id,
                    'punch_time': tx['punch_time'],
                    'punch_state': tx['punch_state'],
                    'terminal_sn': tx['terminal_sn'],
                    'terminal_alias': tx['terminal_alias'],
                    'biotime_transaction_id': tx['id'],
                })

