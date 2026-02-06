import requests
from odoo import models, fields
from odoo.exceptions import UserError
import logging

from datetime import datetime,timedelta
import pytz
from urllib.parse import urlencode, urlparse, parse_qs

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
        # _logger.warning("This is ______________________________ username %s password %s link %s",username,password,base_url)
        return base_url, username, password

    # ------------------------------------------------
    # FETCH TERMINALS
    # ------------------------------------------------

    def _safe_paginated_get(self, start_url, username, password, max_pages=30):
        url = start_url
        seen_urls = set()
        pages = 0
    
        while url and url not in seen_urls and pages < max_pages:
            seen_urls.add(url)
            pages += 1
            # _logger.warning("This is ______________________________pages %s",pages)
    
            res = requests.get(url, auth=(username, password), timeout=30)
            res.raise_for_status()
    
            payload = res.json()
            # _logger.warning("This is ______________________________ payload details %s",payload)
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
    # def sync_attendance(self):
    #     base_url, username, password = self._get_config()
    #     start_url = f"{base_url}/iclock/api/transactions/"
    
    #     HrAttendance = self.env['hr.attendance']
    #     HrAttendanceLine = self.env['hr.attendance.line']
    #     Employee = self.env['hr.employee']
    
    #     grouped = {}
    #     processed_tx_ids = set()  # 🔑 IMPORTANT
    
    #     for payload in self._safe_paginated_get(start_url, username, password):
    #         data = payload.get("data", [])
    
    #         _logger.info("Biotime transactions page fetched: %s records", len(data))
    
    #         for tx in data:
    #             tx_id = tx.get("id")
    #             if not tx_id or tx_id in processed_tx_ids:
    #                 continue
    
    #             processed_tx_ids.add(tx_id)
    
    #             # ⛔ Already exists in DB
    #             if HrAttendanceLine.search(
    #                 [('biotime_transaction_id', '=', tx_id)],
    #                 limit=1
    #             ):
    #                 continue
    
    #             emp_code = tx.get("emp_code")
    #             if not emp_code:
    #                 continue
    
    #             employee = Employee.search(
    #                 [('x_studio_emp_id', '=', emp_code)],
    #                 limit=1
    #             )
    #             if not employee:
    #                 continue
    
    #             # punch_time = fields.Datetime.from_string(tx["punch_time"])
    #             # Biotime sends IST
    #             ist = pytz.timezone("Asia/Kolkata")
                
    #             local_dt = datetime.strptime(
    #                 tx["punch_time"],
    #                 "%Y-%m-%d %H:%M:%S"
    #             )
                
    #             # Attach IST timezone
    #             ist_dt = ist.localize(local_dt)
                
    #             # Convert to UTC
    #             punch_time_utc = ist_dt.astimezone(pytz.UTC)
                
    #             # Convert to Odoo-compatible string
    #             punch_time = fields.Datetime.to_string(punch_time_utc)
    #             date = punch_time.date()
    
    #             grouped.setdefault((employee.id, date), []).append(tx)
    
    #     for (employee_id, date), punches in grouped.items():
    #         punches.sort(key=lambda x: x["punch_time"])
    
    #         attendance = HrAttendance.search([
    #             ('employee_id', '=', employee_id),
    #             ('check_in', '>=', f"{date} 00:00:00"),
    #             ('check_in', '<=', f"{date} 23:59:59"),
    #         ], limit=1)
    
    #         if attendance:
    #             attendance.write({'check_out': punches[-1]["punch_time"]})
    #         else:
    #             attendance = HrAttendance.create({
    #                 'employee_id': employee_id,
    #                 'check_in': punches[0]["punch_time"],
    #                 'check_out': punches[-1]["punch_time"],
    #             })
    
    #         for tx in punches:
    #             HrAttendanceLine.create({
    #                 'attendance_id': attendance.id,
    #                 'employee_id': employee_id,
    #                 'punch_time': tx["punch_time"],
    #                 'punch_state': tx["punch_state"],
    #                 'terminal_sn': tx["terminal_sn"],
    #                 'terminal_alias': tx["terminal_alias"],
    #                 'biotime_transaction_id': tx["id"],
    #             })


    def _safe_paginated_get_line(self, start_url, username, password, max_pages=200):
        url = start_url
        seen_urls = set()
        page = 100
    
        while url:
            if url in seen_urls:
                _logger.warning(
                    "Biotime pagination stopped (repeated URL): %s", url
                )
                break
    
            if page >= max_pages:
                _logger.warning(
                    "Biotime pagination stopped (max pages %s reached)", max_pages
                )
                break
    
            seen_urls.add(url)
            page += 1
    
            _logger.info("Fetching Biotime page %s: %s", page, url)
    
            res = requests.get(url, auth=(username, password), timeout=30)
            res.raise_for_status()
    
            payload = res.json()
            yield payload
    
            next_url = payload.get("next")
    
            # Normalize relative URL
            if next_url and next_url.startswith("/"):
                base = start_url.split("/iclock/api")[0]
                next_url = base + next_url
    
            url = next_url


   

    # def _safe_paginated_get_line_new(
    #     self,
    #     start_url,
    #     username,
    #     password,
    #     start_page=100,
    #     max_pages=200,
    # ):
    #     # -------------------------------------------------
    #     # Force starting page at API level
    #     # -------------------------------------------------
    #     parsed = urlparse(start_url)
    #     query = parse_qs(parsed.query)
    #     query["page"] = [str(start_page)]
    
    #     url = parsed._replace(query=urlencode(query, doseq=True)).geturl()
    
    #     seen_urls = set()
    #     page = start_page
    
    #     while url:
    #         if url in seen_urls:
    #             _logger.warning(
    #                 "Biotime pagination stopped (repeated URL): %s", url
    #             )
    #             break
    
    #         if page > max_pages:
    #             _logger.warning(
    #                 "Biotime pagination stopped (max pages %s reached)", max_pages
    #             )
    #             break
    
    #         seen_urls.add(url)
    
    #         _logger.info("Fetching Biotime page %s: %s", page, url)
    
    #         res = requests.get(url, auth=(username, password), timeout=30)
    #         res.raise_for_status()
    
    #         payload = res.json()
    #         yield payload
    
    #         next_url = payload.get("next")
    
    #         if not next_url:
    #             break
    
    #         # Normalize relative URL
    #         if next_url.startswith("/"):
    #             base = start_url.split("/iclock/api")[0]
    #             next_url = base + next_url
    
    #         url = next_url
    #         page += 1


    # def sync_attendance(self):
    #     base_url, username, password = self._get_config()
    #     start_url = (f"{base_url}/iclock/api/transactions/?ordering=+-id")
    
    #     HrAttendance = self.env['hr.attendance']
    #     HrAttendanceLine = self.env['hr.attendance.line']
    #     Employee = self.env['hr.employee']
    
    #     grouped = {}
    #     processed_tx_ids = set()  # prevents same-run duplicates
    
    #     ist = pytz.timezone("Asia/Kolkata")
    
    #     # for payload in self._safe_paginated_get_line(start_url, username, password):
        
    #     for payload in self._safe_paginated_get_line_new(start_url, username, password,start_page=100,max_pages=200):
    #         data = payload.get("data", [])
    
    #         _logger.info(
    #             "Biotime transactions page fetched: %s records",
    #             len(data)
    #         )
    
    #         for tx in data:
    #             tx_id = tx.get("id")
    #             if not tx_id or tx_id in processed_tx_ids:
    #                 continue
    
    #             processed_tx_ids.add(tx_id)
    
    #             # Skip if already imported in DB
    #             if HrAttendanceLine.search(
    #                 [('biotime_transaction_id', '=', tx_id)],
    #                 limit=1
    #             ):
    #                 continue
    
    #             emp_code = tx.get("emp_code")
    #             if not emp_code:
    #                 continue
    
    #             employee = Employee.search(
    #                 [('x_studio_emp_id', '=', emp_code)],
    #                 limit=1
    #             )
    #             if not employee:
    #                 continue
    
    #             # -------------------------------
    #             # TIMEZONE FIX (IST → UTC)
    #             # -------------------------------
    #             try:
    #                 local_dt = datetime.strptime(
    #                     tx["punch_time"],
    #                     "%Y-%m-%d %H:%M:%S"
    #                 )
    #             except Exception:
    #                 _logger.warning(
    #                     "Invalid punch_time format: %s", tx.get("punch_time")
    #                 )
    #                 continue
    
    #             ist_dt = ist.localize(local_dt)
    #             utc_dt = ist_dt.astimezone(pytz.UTC)
    
    #             # store converted values back into tx
    #             tx["_punch_time_utc"] = fields.Datetime.to_string(utc_dt)
    #             tx["_punch_date_ist"] = ist_dt.date()
    
    #             grouped.setdefault(
    #                 (employee.id, tx["_punch_date_ist"]),
    #                 []
    #             ).append(tx)
    
    #     # ---------------------------------
    #     # CREATE / UPDATE ATTENDANCE
    #     # ---------------------------------
    #     for (employee_id, date), punches in grouped.items():
    #         # Sort by actual UTC time
    #         punches.sort(key=lambda x: x["_punch_time_utc"])
        
    #         check_in = punches[0]["_punch_time_utc"]
    #         check_out = punches[-1]["_punch_time_utc"]
        
    #         # ⛔ ABSOLUTE SAFETY (Odoo core constraint)
    #         if check_out < check_in:
    #             _logger.warning(
    #                 "Skipping invalid attendance (night-shift split needed): emp=%s date=%s",
    #                 employee_id, date
    #             )
    #             continue
        
    #         attendance = HrAttendance.search([
    #             ('employee_id', '=', employee_id),
    #             ('check_in', '>=', f"{date} 00:00:00"),
    #             ('check_in', '<=', f"{date} 23:59:59"),
    #         ], limit=1)
        
    #         # if attendance:
    #         #     attendance.write({
    #         #         'check_out': check_out
    #         #     })
    #         if attendance:
    # # FINAL SAFETY CHECK (Odoo hard constraint)
    #             if check_out <= attendance.check_in:
    #                 _logger.warning(
    #                     "Skipping invalid attendance update "
    #                     "(check_out <= check_in): emp=%s attendance=%s "
    #                     "check_in=%s check_out=%s",
    #                     employee_id,
    #                     attendance.id,
    #                     attendance.check_in,
    #                     check_out,
    #                 )
    #                 continue
            
    #             attendance.write({
    #                 'check_out': check_out
    #             })

    #         else:
    #             # attendance = HrAttendance.create({
    #             #     'employee_id': employee_id,
    #             #     'check_in': check_in,
    #             #     'check_out': check_out,
    #             # })
    #             if check_out <= check_in:
    #                 _logger.warning(
    #                     "Skipping invalid attendance CREATE "
    #                     "(check_out <= check_in): emp=%s date=%s "
    #                     "check_in=%s check_out=%s",
    #                     employee_id,
    #                     date,
    #                     check_in,
    #                     check_out,
    #                 )
    #                 continue
                
    #             attendance = HrAttendance.create({
    #                 'employee_id': employee_id,
    #                 'check_in': check_in,
    #                 'check_out': check_out,
    #             })

        
    #         # ---------------------------------
    #         # ✅ ALWAYS CREATE ATTENDANCE LINES
    #         # ---------------------------------
    #         for tx in punches:
    #             # Double safety: prevent duplicate lines
    #             if HrAttendanceLine.search(
    #                 [('biotime_transaction_id', '=', tx["id"])],
    #                 limit=1
    #             ):
    #                 continue
        
    #             HrAttendanceLine.create({
    #                 'attendance_id': attendance.id,
    #                 'employee_id': employee_id,
    #                 'punch_time': tx["_punch_time_utc"],
    #                 'punch_state': tx.get("punch_state"),
    #                 'terminal_sn': tx.get("terminal_sn"),
    #                 'terminal_alias': tx.get("terminal_alias"),
    #                 'biotime_transaction_id': tx["id"],
    #             })






    def _sanitize_punch_state(self, value):
        """
        Biotime sometimes sends invalid punch_state (e.g. 255).
        Allow only '0' or '1', else return False.
        """
        if value in (0, 1, '0', '1'):
            return str(value)
        return False

    
    
    
    
    
    def _safe_paginated_get_line_new(
        self,
        start_url,
        username,
        password,
        start_page=100,
        max_pages=200,
    ):
        parsed = urlparse(start_url)
        query = parse_qs(parsed.query)
        query["page"] = [str(start_page)]
    
        url = parsed._replace(query=urlencode(query, doseq=True)).geturl()
    
        seen_urls = set()
        page = start_page
    
        while url:
            if url in seen_urls:
                _logger.warning("Biotime pagination stopped (repeated URL): %s", url)
                break
    
            if page > max_pages:
                _logger.warning("Biotime pagination stopped (max pages %s reached)", max_pages)
                break
    
            seen_urls.add(url)
    
            _logger.info("Fetching Biotime page %s: %s", page, url)
    
            res = requests.get(url, auth=(username, password), timeout=30)
            res.raise_for_status()
    
            payload = res.json()
            yield payload
    
            next_url = payload.get("next")
            if not next_url:
                break
    
            if next_url.startswith("/"):
                base = start_url.split("/iclock/api")[0]
                next_url = base + next_url
    
            url = next_url
            page += 1



    def _auto_close_old_attendance(self, employee, new_check_in):
        """
        If there is an open attendance and 15 minutes passed,
        auto close it and mark x_studio_no_checkout = True
        """
        HrAttendance = self.env['hr.attendance']
    
        open_attendance = HrAttendance.search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False),
        ], limit=1)
    
        if not open_attendance:
            return
    
        check_in = open_attendance.check_in
        if not check_in:
            return
    
        # ensure datetime comparison
        if isinstance(check_in, str):
            check_in = fields.Datetime.from_string(check_in)
    
        if new_check_in >= check_in + timedelta(minutes=15):
            auto_checkout = check_in + timedelta(minutes=15)
    
            _logger.warning(
                "Auto closing attendance (no checkout): emp=%s "
                "check_in=%s auto_check_out=%s",
                employee.id,
                check_in,
                auto_checkout,
            )
    
            open_attendance.write({
                'check_out': auto_checkout,
                'x_studio_no_checkout': True,
            })

    


    def sync_attendance(self):
        base_url, username, password = self._get_config()
        start_url = f"{base_url}/iclock/api/transactions/?ordering=+-id"
    
        HrAttendance = self.env['hr.attendance']
        HrAttendanceLine = self.env['hr.attendance.line']
        Employee = self.env['hr.employee']
    
        grouped = {}
        processed_tx_ids = set()
    
        ist = pytz.timezone("Asia/Kolkata")
    
        for payload in self._safe_paginated_get_line_new(
            start_url,
            username,
            password,
            start_page=100,
            max_pages=200,
        ):
            data = payload.get("data", [])
    
            _logger.info("Biotime transactions page fetched: %s records", len(data))
    
            for tx in data:
                tx_id = tx.get("id")
                if not tx_id or tx_id in processed_tx_ids:
                    continue
    
                processed_tx_ids.add(tx_id)
    
                # Prevent duplicates
                if HrAttendanceLine.search(
                    [('biotime_transaction_id', '=', tx_id)],
                    limit=1
                ):
                    continue
    
                emp_code = tx.get("emp_code")
                if not emp_code:
                    continue
    
                employee = Employee.search(
                    [('x_studio_emp_id', '=', emp_code)],
                    limit=1
                )
                if not employee:
                    continue
    
                try:
                    local_dt = datetime.strptime(
                        tx["punch_time"], "%Y-%m-%d %H:%M:%S"
                    )
                except Exception:
                    _logger.warning("Invalid punch_time format: %s", tx.get("punch_time"))
                    continue
    
                ist_dt = ist.localize(local_dt)
                utc_dt = ist_dt.astimezone(pytz.UTC).replace(tzinfo=None)
    
                tx["_punch_time_utc"] = utc_dt
                tx["_punch_date_ist"] = ist_dt.date()
    
                grouped.setdefault(
                    (employee.id, tx["_punch_date_ist"]),
                    []
                ).append(tx)
    
     
        # ---------------------------------
        # CREATE / UPDATE ATTENDANCE
        # ---------------------------------
        for (employee_id, date), punches in grouped.items():
            punches.sort(key=lambda x: x["_punch_time_utc"])
        
            check_in = punches[0]["_punch_time_utc"]
            check_out = punches[-1]["_punch_time_utc"]
            
            self._auto_close_old_attendance(employee, check_in)
        
            attendance = HrAttendance.search([
                ('employee_id', '=', employee_id),
                ('check_in', '>=', f"{date} 00:00:00"),
                ('check_in', '<=', f"{date} 23:59:59"),
            ], limit=1)
        
            # ----------------------------
            # ✅ SINGLE PUNCH DAY
            # ----------------------------
            if len(punches) == 1:
                if attendance:
                    _logger.info(
                        "Single punch already has attendance: emp=%s date=%s",
                        employee_id, date
                    )
                else:
                    HrAttendance.create({
                        'employee_id': employee_id,
                        'check_in': check_in,
                        # check_out intentionally NOT set
                    })
        
                _logger.info(
                    "Single punch → attendance check_in only: emp=%s date=%s",
                    employee_id, date
                )
                continue
        
            # ----------------------------
            # ✅ MULTIPLE PUNCHES
            # ----------------------------
            if check_out <= check_in:
                _logger.warning(
                    "Skipping invalid attendance (check_out <= check_in): emp=%s date=%s",
                    employee_id, date
                )
                continue
        
            if attendance:
                if attendance.check_out and check_out <= attendance.check_in:
                    _logger.warning(
                        "Skipping invalid attendance UPDATE: emp=%s attendance=%s",
                        employee_id,
                        attendance.id,
                    )
                    continue
        
                attendance.write({
                    'check_out': check_out
                })
            else:
                HrAttendance.create({
                    'employee_id': employee_id,
                    'check_in': check_in,
                    'check_out': check_out,
                })

      
            # ---------------------------------
            # ✅ ALWAYS CREATE ATTENDANCE LINES
            # ---------------------------------
            for tx in punches:
                # Double safety: prevent duplicate lines
                if HrAttendanceLine.search(
                    [('biotime_transaction_id', '=', tx["id"])],
                    limit=1
                ):
                    continue
        
                HrAttendanceLine.create({
                    'attendance_id': attendance.id,
                    'employee_id': employee_id,
                    'punch_time': tx["_punch_time_utc"],
                    'punch_state': self._sanitize_punch_state(tx.get("punch_state")),
                    'terminal_sn': tx.get("terminal_sn"),
                    'terminal_alias': tx.get("terminal_alias"),
                    'biotime_transaction_id': tx["id"],
                })





