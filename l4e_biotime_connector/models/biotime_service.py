import requests
from odoo import models, fields , api
from odoo.exceptions import UserError
import logging

from datetime import datetime,timedelta , time
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


    def _sanitize_punch_state(self, value):
        """
        Biotime sometimes sends invalid punch_state (e.g. 255).
        Allow only '0' or '1', else return False.
        """
        if value in (0, 1, '0', '1'):
            return str(value)
        return False

    
    
    
    

    def _safe_paginated_get_line_new(self,start_url,username,password,start_page=1,max_pages=40):
        parsed = urlparse(start_url)
        query = parse_qs(parsed.query)
        query["page"] = [str(start_page)]
    
        url = parsed._replace(
            query=urlencode(query, doseq=True)
        ).geturl()
    
        seen_urls = set()
        page_count = 0  # 🔥 real limiter
    
        while url:
            if url in seen_urls:
                _logger.warning(
                    "Biotime pagination stopped (repeated URL): %s", url
                )
                break
    
            if page_count >= max_pages:
                _logger.warning(
                    "Biotime pagination stopped (max pages %s reached)",
                    max_pages
                )
                break
    
            seen_urls.add(url)
    
            _logger.info(
                "Fetching Biotime page #%s: %s",
                page_count,
                url
            )
    
            res = requests.get(
                url,
                auth=(username, password),
                timeout=30
            )
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
            page_count += 1
    
        
        


    def _auto_close_old_attendance(self, employee, new_check_in):
      
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
    
        # ------------------------------------------------
        # FETCH TRANSACTIONS
        # ------------------------------------------------
        for payload in self._safe_paginated_get_line_new(
                start_url, username, password,
                start_page=1, max_pages=40):
    
            data = payload.get("data", [])
    
            for tx in data:
    
                tx_id = tx.get("id")
                if not tx_id or tx_id in processed_tx_ids:
                    continue
    
                processed_tx_ids.add(tx_id)
    
                # Prevent duplicate punch import
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
                    continue
    
                ist_dt = ist.localize(local_dt)
                utc_dt = ist_dt.astimezone(pytz.UTC).replace(tzinfo=None)
    
                tx["_punch_time_utc"] = utc_dt
                tx["_punch_date_ist"] = ist_dt.date()
    
                grouped.setdefault(
                    (employee.id, tx["_punch_date_ist"]),
                    []
                ).append(tx)
    
        # ------------------------------------------------
        # PROCESS GROUPED ATTENDANCE
        # ------------------------------------------------
        for (employee_id, date), punches in grouped.items():
    
            punches.sort(key=lambda x: x["_punch_time_utc"])
    
            check_in = punches[0]["_punch_time_utc"]
            check_out = punches[-1]["_punch_time_utc"]
    
            employee_rec = Employee.browse(employee_id)
    
            # ------------------------------------------------
            # STEP 1: CLOSE ANY OPEN ATTENDANCE SAFELY
            # ------------------------------------------------
            open_attendance = HrAttendance.search([
                ('employee_id', '=', employee_id),
                ('check_out', '=', False),
            ], limit=1)
    
            if open_attendance:
                # Close it at new check_in time if valid
                if check_in > open_attendance.check_in:
                    open_attendance.write({
                        'check_out': check_in,
                        'x_studio_no_checkout': True,
                    })
    
            # ------------------------------------------------
            # STEP 2: RECHECK OPEN ATTENDANCE
            # ------------------------------------------------
            attendance = HrAttendance.search([
                ('employee_id', '=', employee_id),
                ('check_out', '=', False),
            ], limit=1)
    
            if not attendance:
                # Safe to create new attendance
                attendance = HrAttendance.create({
                    'employee_id': employee_id,
                    'check_in': check_in,
                })
    
            # ------------------------------------------------
            # STEP 3: UPDATE CHECKOUT IF VALID
            # ------------------------------------------------
            if check_out and check_out > attendance.check_in:
                attendance.write({
                    'check_out': check_out,
                    'x_studio_no_checkout': False,
                })
    
            # ------------------------------------------------
            # STEP 4: CREATE PUNCH LINES
            # ------------------------------------------------
            for tx in punches:
    
                if HrAttendanceLine.search(
                    [('biotime_transaction_id', '=', tx["id"])],
                    limit=1
                ):
                    continue
    
                HrAttendanceLine.create({
                    'attendance_id': attendance.id,
                    'employee_id': employee_id,
                    'punch_time': tx["_punch_time_utc"],
                    'punch_state': self._sanitize_punch_state(
                        tx.get("punch_state")
                    ),
                    'terminal_sn': tx.get("terminal_sn"),
                    'terminal_alias': tx.get("terminal_alias"),
                    'biotime_transaction_id': tx["id"],
                })


    # def sync_attendance(self):

    #     base_url, username, password = self._get_config()
    #     start_url = f"{base_url}/iclock/api/transactions/?ordering=+-id"
    
    #     HrAttendance = self.env['hr.attendance']
    #     HrAttendanceLine = self.env['hr.attendance.line']
    #     Employee = self.env['hr.employee']
    
    #     grouped = {}
    #     processed_tx_ids = set()
    
    #     ist = pytz.timezone("Asia/Kolkata")
    
    #     # ------------------------------------------------
    #     # FETCH TRANSACTIONS
    #     # ------------------------------------------------
    #     for payload in self._safe_paginated_get_line_new(
    #             start_url, username, password,
    #             start_page=1, max_pages=40):
    
    #         data = payload.get("data", [])
    
    #         for tx in data:
    
    #             tx_id = tx.get("id")
    #             if not tx_id or tx_id in processed_tx_ids:
    #                 continue
    
    #             processed_tx_ids.add(tx_id)
    
    #             # Prevent duplicate import
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
    
    #             try:
    #                 local_dt = datetime.strptime(
    #                     tx["punch_time"], "%Y-%m-%d %H:%M:%S"
    #                 )
    #             except Exception:
    #                 continue
    
    #             ist_dt = ist.localize(local_dt)
    #             utc_dt = ist_dt.astimezone(pytz.UTC).replace(tzinfo=None)
    
    #             tx["_punch_time_utc"] = utc_dt
    #             tx["_punch_date_ist"] = ist_dt.date()
    
    #             grouped.setdefault(
    #                 (employee.id, tx["_punch_date_ist"]),
    #                 []
    #             ).append(tx)
    
    #     # ------------------------------------------------
    #     # PROCESS GROUPED ATTENDANCE
    #     # ------------------------------------------------
    #     for (employee_id, date), punches in grouped.items():
    
    #         punches.sort(key=lambda x: x["_punch_time_utc"])
    
    #         check_in = punches[0]["_punch_time_utc"]
    #         check_out = punches[-1]["_punch_time_utc"]
    
    #         employee_rec = Employee.browse(employee_id)
    
    #         # ------------------------------------------------
    #         # FORCE CLOSE ANY OPEN ATTENDANCE (ENTERPRISE SAFE)
    #         # ------------------------------------------------
    #         open_attendance = HrAttendance.search([
    #             ('employee_id', '=', employee_id),
    #             ('check_out', '=', False),
    #         ], limit=1)
    
    #         if open_attendance:
    
    #             check_in_utc = fields.Datetime.to_datetime(open_attendance.check_in)
    #             check_in_ist = pytz.UTC.localize(check_in_utc).astimezone(ist)
    
    #             seven_pm_ist = ist.localize(
    #                 datetime.combine(check_in_ist.date(), time(19, 0, 0))
    #             )
    
    #             seven_pm_utc = seven_pm_ist.astimezone(pytz.UTC).replace(tzinfo=None)
    
    #             if seven_pm_utc > check_in_utc:
    #                 open_attendance.write({
    #                     'check_out': seven_pm_utc,
    #                     'x_studio_no_checkout': True,
    #                 })
    
           
    #         # Find open attendance first
    #         attendance = HrAttendance.search([
    #             ('employee_id', '=', employee_id),
    #             ('check_out', '=', False),
    #         ], limit=1)
            
    #         if attendance:
    #             # Update checkout when real checkout arrives
    #             if check_out > attendance.check_in:
    #                 attendance.write({
    #                     'check_out': check_out,
    #                     'x_studio_no_checkout': False,
    #                 })
    #         else:
    #             # No open attendance → create new
    #             attendance = HrAttendance.create({
    #                 'employee_id': employee_id,
    #                 'check_in': check_in,
    #                 'check_out': check_out if check_out > check_in else False,
    #             })

    
    #         # ------------------------------------------------
    #         # CREATE ALL PUNCH LINES
    #         # ------------------------------------------------
    #         for tx in punches:
    
    #             if HrAttendanceLine.search(
    #                 [('biotime_transaction_id', '=', tx["id"])],
    #                 limit=1
    #             ):
    #                 continue
    
    #             HrAttendanceLine.create({
    #                 'attendance_id': attendance.id,
    #                 'employee_id': employee_id,
    #                 'punch_time': tx["_punch_time_utc"],
    #                 'punch_state': self._sanitize_punch_state(
    #                     tx.get("punch_state")
    #                 ),
    #                 'terminal_sn': tx.get("terminal_sn"),
    #                 'terminal_alias': tx.get("terminal_alias"),
    #                 'biotime_transaction_id': tx["id"],
    #             })
    





    @api.model
    def cron_auto_close_attendance_7pm(self):
        """
        Auto close ALL open attendances
        and set checkout to 7:00 PM IST
        """
    
        HrAttendance = self.env['hr.attendance']
        ist = pytz.timezone("Asia/Kolkata")
    
        open_attendances = HrAttendance.search([
            ('check_out', '=', False),
        ])
    
        for attendance in open_attendances:
    
            if not attendance.check_in:
                continue
    
            # Convert check_in (UTC) → IST
            check_in_utc = fields.Datetime.to_datetime(attendance.check_in)
            check_in_ist = pytz.UTC.localize(check_in_utc).astimezone(ist)
    
            # Build 7PM IST of that date
            seven_pm_ist = ist.localize(
                datetime.combine(check_in_ist.date(), time(19, 0, 0))
            )
    
            # Convert back to UTC for storage
            seven_pm_utc = seven_pm_ist.astimezone(pytz.UTC).replace(tzinfo=None)
    
            # Prevent invalid checkout
            if seven_pm_utc <= check_in_utc:
                continue
    
            attendance.write({
                'check_out': seven_pm_utc,
                'x_studio_no_checkout': True,
            })
    
            _logger.info(
                "Auto-closed attendance at 7PM IST: emp=%s attendance=%s",
                attendance.employee_id.id,
                attendance.id,
            )







