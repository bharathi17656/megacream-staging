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

    def _safe_paginated_get(self, start_url, username, password, max_pages=50):
        url = start_url
        seen_urls = set()
        pages = 0
    
        while url and url not in seen_urls and pages < max_pages:
            seen_urls.add(url)
            pages += 1
            _logger.warning("This is ______________________________pages %s",pages)
    
            res = requests.get(url, auth=(username, password), timeout=30)
            res.raise_for_status()
    
            payload = res.json()
            _logger.warning("This is ______________________________ payload details %s",payload)
            yield payload
    
            url = payload.get("next")

    
    def sync_terminals(self):
        base_url, username, password = self._get_config()
        url = f"{base_url}/iclock/api/terminals/"

        res = requests.get(url, auth=(username, password), timeout=30)
        res.raise_for_status()
        _logger.warning("This is ______________________________ record terminal %s",res)

        _logger.warning(
            "Biotime terminal API response: status=%s, count=%s",
            res.status_code,
            len(res.json().get('data', []))
        )

        Terminal = self.env['biotime.terminal']
        data = res.json().get('data', [])

        for t in data:

            terminal = Terminal.search([
                ('biotime_id', '=', t['id'])
            ], limit=1)
            
            vals = {
                'biotime_id': t.get('id'),
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
            }
            
            if terminal:
                terminal.write(vals)
            else:
                Terminal.create(vals)

    # ------------------------------------------------
    # FETCH BIODATA
    # ------------------------------------------------
    # def sync_biodata(self):
    #     base_url, username, password = self._get_config()
    #     url = f"{base_url}/iclock/api/biodatas/"
    
    #     Biodata = self.env['biotime.biodata']
    #     Employee = self.env['hr.employee']
    
    #     while url:
    #         res = requests.get(url, auth=(username, password), timeout=30)
    #         res.raise_for_status()
    #         payload = res.json()
    
    #         data = payload.get('data', [])
    
    #         _logger.info(
    #             "Biotime biodata API response: count=%s",
    #             len(data)
    #         )
    
    #         for b in data:
    #             if not b.get('employee'):
    #                 continue
    
    #             emp_code = b['employee'].split()[0]
    
    #             employee = Employee.search([
    #                 ('biotime_emp_code', '=', emp_code)
    #             ], limit=1)
    
    #             biodata = Biodata.search([
    #                 ('biotime_id', '=', b.get('id'))
    #             ], limit=1)
    
    #             vals = {
    #                 'employee_name': b.get('employee'),
    #                 'emp_code': emp_code,
    #                 'bio_type': b.get('bio_type'),
    #                 'bio_no': b.get('bio_no'),
    #                 'bio_index': b.get('bio_index'),
    #                 'bio_tmp': b.get('bio_tmp'),
    #                 'major_ver': b.get('major_ver'),
    #                 'update_time': b.get('update_time'),
    #                 'employee_id': employee.id if employee else False,
    #             }
    
    #             if biodata:
    #                 biodata.write(vals)
    #             else:
    #                 vals['biotime_id'] = b.get('id')


    def sync_biodata(self):
        base_url, username, password = self._get_config()
        start_url = f"{base_url}/iclock/api/biodatas/"
    
        Biodata = self.env['biotime.biodata']
        Employee = self.env['hr.employee']
    
        for payload in self._safe_paginated_get(start_url, username, password):
            data = payload.get("data", [])
    
            _logger.info("Biotime biodata page fetched: %s records", len(data))
    
            for b in data:
                if not b.get("employee"):
                    continue
    
                emp_code = b["employee"].split()[0]
    
                employee = Employee.search(
                    [('x_studio_emp_id', '=', emp_code)],
                    limit=1
                )
    
                biodata = Biodata.search(
                    [('biotime_id', '=', b.get("id"))],
                    limit=1
                )
    
                vals = {
                    'employee_name': b.get('employee'),
                    'emp_code': emp_code,
                    'bio_type': b.get('bio_type'),
                    'bio_no': b.get('bio_no'),
                    'bio_index': b.get('bio_index'),
                    'bio_tmp': b.get('bio_tmp'),
                    'major_ver': b.get('major_ver'),
                    'update_time': b.get('update_time'),
                    'employee_id': employee.id if employee else False,
                }
    
                if biodata:
                    biodata.write(vals)
                else:
                    vals['biotime_id'] = b.get('id')
                    Biodata.create(vals)



    # ------------------------------------------------
    # FETCH TRANSACTIONS → ATTENDANCE
    # ------------------------------------------------
    # def sync_attendance(self):
    #     base_url, username, password = self._get_config()
    #     url = f"{base_url}/iclock/api/transactions/"
    
    #     HrAttendance = self.env['hr.attendance']
    #     HrAttendanceLine = self.env['hr.attendance.line']
    #     Employee = self.env['hr.employee']
    
    #     grouped = {}
    
    #     while url:
    #         res = requests.get(url, auth=(username, password), timeout=30)
    #         res.raise_for_status()
    #         payload = res.json()
    
    #         data = payload.get('data', [])
    
    #         _logger.info(
    #             "Biotime transaction API response: count=%s",
    #             len(data)
    #         )
    
    #         for tx in data:
    #             emp_code = tx.get('emp_code')
    #             if not emp_code:
    #                 continue
    
    #             employee = Employee.search([
    #                 ('biotime_emp_code', '=', emp_code)
    #             ], limit=1)
    
    #             if not employee:
    #                 continue
    
    #             punch_time = fields.Datetime.from_string(tx['punch_time'])
    #             date = punch_time.date()
    
    #             grouped.setdefault(
    #                 (employee.id, date),
    #                 []
    #             ).append(tx)
    
    #         url = payload.get('next')
    
    #     for (employee_id, date), punches in grouped.items():
    #         punches.sort(key=lambda x: x['punch_time'])
    
    #         attendance = HrAttendance.search([
    #             ('employee_id', '=', employee_id),
    #             ('check_in', '>=', f"{date} 00:00:00"),
    #             ('check_in', '<=', f"{date} 23:59:59"),
    #         ], limit=1)
    
    #         if attendance:
    #             attendance.write({
    #                 'check_out': punches[-1]['punch_time']
    #             })
    #         else:
    #             attendance = HrAttendance.create({
    #                 'employee_id': employee_id,
    #                 'check_in': punches[0]['punch_time'],
    #                 'check_out': punches[-1]['punch_time'],
    #             })
    
    #         for tx in punches:
    #             exists = HrAttendanceLine.search([
    #                 ('biotime_transaction_id', '=', tx.get('id'))
    #             ], limit=1)
    
    #             if exists:
    #                 continue
    
    #             HrAttendanceLine.create({
    #                 'attendance_id': attendance.id,
    #                 'employee_id': employee_id,
    #                 'punch_time': tx.get('punch_time'),
    #                 'punch_state': tx.get('punch_state'),
    #                 'terminal_sn': tx.get('terminal_sn'),
    #                 'terminal_alias': tx.get('terminal_alias'),
    #                 'biotime_transaction_id': tx.get('id'),
    #             })
    def sync_attendance(self):
        base_url, username, password = self._get_config()
        start_url = f"{base_url}/iclock/api/transactions/"
    
        HrAttendance = self.env['hr.attendance']
        HrAttendanceLine = self.env['hr.attendance.line']
        Employee = self.env['hr.employee']
    
        grouped = {}
        processed_tx_ids = set()  # 🔑 IMPORTANT
    
        for payload in self._safe_paginated_get(start_url, username, password):
            data = payload.get("data", [])
    
            _logger.info("Biotime transactions page fetched: %s records", len(data))
    
            for tx in data:
                tx_id = tx.get("id")
                if not tx_id or tx_id in processed_tx_ids:
                    continue
    
                processed_tx_ids.add(tx_id)
    
                # ⛔ Already exists in DB
                if HrAttendanceLine.search(
                    [('biotime_transaction_id', '=', tx_id)],
                    limit=1
                ):
                    continue
    
                emp_code = tx.get("emp_code")
                if not emp_code:
                    continue
    
                employee = Employee.search(
                    [('biotime_emp_code', '=', emp_code)],
                    limit=1
                )
                if not employee:
                    continue
    
                punch_time = fields.Datetime.from_string(tx["punch_time"])
                date = punch_time.date()
    
                grouped.setdefault((employee.id, date), []).append(tx)
    
        for (employee_id, date), punches in grouped.items():
            punches.sort(key=lambda x: x["punch_time"])
    
            attendance = HrAttendance.search([
                ('employee_id', '=', employee_id),
                ('check_in', '>=', f"{date} 00:00:00"),
                ('check_in', '<=', f"{date} 23:59:59"),
            ], limit=1)
    
            if attendance:
                attendance.write({'check_out': punches[-1]["punch_time"]})
            else:
                attendance = HrAttendance.create({
                    'employee_id': employee_id,
                    'check_in': punches[0]["punch_time"],
                    'check_out': punches[-1]["punch_time"],
                })
    
            for tx in punches:
                HrAttendanceLine.create({
                    'attendance_id': attendance.id,
                    'employee_id': employee_id,
                    'punch_time': tx["punch_time"],
                    'punch_state': tx["punch_state"],
                    'terminal_sn': tx["terminal_sn"],
                    'terminal_alias': tx["terminal_alias"],
                    'biotime_transaction_id': tx["id"],
                })
