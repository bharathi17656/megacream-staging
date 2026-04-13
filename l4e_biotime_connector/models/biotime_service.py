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

    name = fields.Char(
            string="Name",
            default="Biotime Control Panel",
            readonly=True
    )

    # @api.model
    # def create(self, vals):
    #     if self.search_count([]) >= 1:
    #         raise UserError("Biotime Control Panel already exists.")
    #     return super().create(vals)

    # def unlink(self):
    #     raise UserError("You cannot delete Biotime Control Panel.")


    
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

    
    
    
    

    def _safe_paginated_get_line_new(self,start_url,username,password,start_page=1,max_pages=6):
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






    def _reset_and_revalidate_work_entries(self, employee_id):
        """Reset all validated work entries for employee to draft,
        return them so caller can re-validate after attendance is updated."""
        _logger = logging.getLogger(__name__)
        WorkEntry = self.env['hr.work.entry']
        entries = WorkEntry.search([
            ('employee_id', '=', employee_id),
            ('state', '=', 'validated'),
        ])
        if entries:
            _logger.info(
                f"  → Resetting {len(entries)} validated work entry(ies) to draft "
                f"for Employee {employee_id}"
            )
            entries.write({'state': 'draft'})
        return entries

    def _revalidate_work_entries(self, entries):
        """Re-validate work entries after attendance update."""
        _logger = logging.getLogger(__name__)
        if not entries:
            return
        try:
            entries.action_validate()
        except AttributeError:
            entries.write({'state': 'validated'})
        _logger.info(f"  → Re-validated {len(entries)} work entry(ies) ✓")

    def sync_attendance(self):
    
        _logger = logging.getLogger(__name__)
        _logger.info("=== BIOTIME SYNC STARTED ===")
    
        base_url, username, password = self._get_config()
    
        HrAttendance = self.env['hr.attendance']
        HrAttendanceLine = self.env['hr.attendance.line']
        Employee = self.env['hr.employee']
    
        ist = pytz.timezone("Asia/Kolkata")
    
        today_ist = datetime.now(ist).date()
        _logger.info(f"Syncing only from today: {today_ist}")
    
        start_url = f"{base_url}/iclock/api/transactions/?ordering=+-id"
    
        all_transactions = []
        page_count = 0
        max_pages = 25
        url = start_url
    
        # =====================================================
        # 1️⃣ FETCH LATEST 6 PAGES
        # =====================================================
        while url and page_count < max_pages:
    
            _logger.info(f"Fetching page {page_count + 1}")

            try:
                res = requests.get(url, auth=(username, password), timeout=60)
                res.raise_for_status()
            except requests.exceptions.Timeout:
                _logger.warning(f"BioTime API timed out on page {page_count + 1}, stopping fetch with {len(all_transactions)} transactions so far")
                break
            except requests.exceptions.RequestException as e:
                _logger.warning(f"BioTime API error on page {page_count + 1}: {e}, stopping fetch")
                break

            payload = res.json()
            data = payload.get("data", [])

            if not data:
                break

            all_transactions.extend(data)
    
            url = payload.get("next")
            page_count += 1
    
        if not all_transactions:
            _logger.info("No transactions found.")
            return
    
        _logger.info(f"Total transactions fetched: {len(all_transactions)}")
    
        # =====================================================
        # 2️⃣ SORT BY punch_time ASC
        # =====================================================
        def parse_time(tx):
            try:
                return datetime.strptime(tx["punch_time"], "%Y-%m-%d %H:%M:%S")
            except:
                return datetime.min
    
        all_transactions.sort(key=parse_time)
    
        # =====================================================
        # 3️⃣ GROUP BY EMPLOYEE + DATE (ONLY TODAY)
        # =====================================================
        grouped = {}
    
        for tx in all_transactions:
    
            tx_id = tx.get("id")
            emp_code = tx.get("emp_code")
    
            if not tx_id or not emp_code:
                continue
    
            # Skip already imported punch
            if HrAttendanceLine.search(
                [('biotime_transaction_id', '=', tx_id)],
                limit=1
            ):
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
            except:
                continue
    
            ist_dt = ist.localize(local_dt)
    
            # 🔴 SKIP OLD DATES
            # if ist_dt.date() < today_ist:
            #     continue
    
            utc_dt = ist_dt.astimezone(pytz.UTC).replace(tzinfo=None)
            punch_date = ist_dt.date()
    
            grouped.setdefault(
                (employee.id, punch_date),
                []
            ).append({
                "tx_id": tx_id,
                "punch_time": utc_dt,
                "terminal_sn": tx.get("terminal_sn"),
                "terminal_alias": tx.get("terminal_alias"),
            })
    
        _logger.info(f"Employees to process: {len(grouped)}")
    
        # =====================================================
        # 4️⃣ PROCESS
        # =====================================================
        for (employee_id, punch_date), punches in grouped.items():
    
            punches.sort(key=lambda x: x["punch_time"])
    
            first_punch = punches[0]["punch_time"]
            last_punch = punches[-1]["punch_time"]
    
            punch_times_ist = [
                pytz.UTC.localize(p["punch_time"]).astimezone(ist).strftime("%H:%M")
                for p in punches
            ]
            _logger.info(
                f"Processing Employee {employee_id} "
                f"{punch_date} | Punches: {len(punches)} | Times(IST): {punch_times_ist}"
            )

            # -----------------------------------------------
            # FIND EXISTING ATTENDANCE FOR SAME DAY
            # -----------------------------------------------
            day_start_utc = ist.localize(
                datetime.combine(punch_date, time(0, 0, 0))
            ).astimezone(pytz.UTC).replace(tzinfo=None)
            day_end_utc = ist.localize(
                datetime.combine(punch_date, time(23, 59, 59))
            ).astimezone(pytz.UTC).replace(tzinfo=None)

            existing = HrAttendance.search([
                ('employee_id', '=', employee_id),
                ('check_in', '>=', day_start_utc),
                ('check_in', '<=', day_end_utc),
            ], limit=1)

            if existing:

                existing_in_ist = pytz.UTC.localize(existing.check_in).astimezone(ist).strftime("%H:%M")
                existing_out_ist = (
                    pytz.UTC.localize(existing.check_out).astimezone(ist).strftime("%H:%M")
                    if existing.check_out else "None"
                )
                _logger.info(
                    f"  → Found existing attendance ID {existing.id} | "
                    f"check_in={existing_in_ist} check_out={existing_out_ist} IST"
                )

                new_checkin = min(existing.check_in, first_punch)
                new_checkout = max(
                    existing.check_out or last_punch,
                    last_punch
                )
                has_checkout = new_checkout != new_checkin

                new_in_ist = pytz.UTC.localize(new_checkin).astimezone(ist).strftime("%H:%M")
                new_out_ist = pytz.UTC.localize(new_checkout).astimezone(ist).strftime("%H:%M") if has_checkout else "None"
                _logger.info(
                    f"  → Will write: check_in={new_in_ist} check_out={new_out_ist} IST "
                    f"no_checkout={not has_checkout}"
                )

                try:
                    with self.env.cr.savepoint():
                        existing.write({
                            'check_in': new_checkin,
                            'check_out': new_checkout if has_checkout else False,
                            'x_studio_no_checkout': not has_checkout,
                        })
                    attendance = existing
                    _logger.info(f"  → Updated existing attendance ID {attendance.id} ✓")
                except Exception:
                    # Reset validated work entries, retry, then re-validate
                    work_entries = self._reset_and_revalidate_work_entries(employee_id)
                    try:
                        with self.env.cr.savepoint():
                            existing.write({
                                'check_in': new_checkin,
                                'check_out': new_checkout if has_checkout else False,
                                'x_studio_no_checkout': not has_checkout,
                            })
                        attendance = existing
                        _logger.info(f"  → Updated existing attendance ID {attendance.id} ✓ (after work entry reset)")
                    except Exception as e2:
                        _logger.warning(f"  → SKIPPED attendance ID {existing.id} even after reset: {e2}")
                        attendance = existing
                    finally:
                        self._revalidate_work_entries(work_entries)

            else:

                _logger.info(f"  → No existing attendance found for Employee {employee_id} on {punch_date}")

                # Close any open previous-day record before creating new one
                open_prev = HrAttendance.search([
                    ('employee_id', '=', employee_id),
                    ('check_out', '=', False),
                    ('check_in', '<', day_start_utc),
                ], limit=1)

                if open_prev:
                    prev_checkin_ist = pytz.UTC.localize(
                        open_prev.check_in
                    ).astimezone(ist)
                    prev_date = prev_checkin_ist.date()
                    if prev_checkin_ist.time() < time(19, 0, 0):
                        close_ist = ist.localize(
                            datetime.combine(prev_date, time(19, 0, 0))
                        )
                    else:
                        close_ist = prev_checkin_ist + timedelta(minutes=15)
                    close_utc = close_ist.astimezone(pytz.UTC).replace(tzinfo=None)

                    _logger.info(
                        f"  → Open previous attendance ID {open_prev.id} found "
                        f"(check_in={prev_checkin_ist.strftime('%Y-%m-%d %H:%M')} IST) — "
                        f"will close at {close_ist.strftime('%H:%M')} IST"
                    )

                    try:
                        with self.env.cr.savepoint():
                            open_prev.write({
                                'check_out': close_utc,
                                'x_studio_no_checkout': True,
                            })
                        _logger.info(
                            f"  → Auto-closed attendance ID {open_prev.id} "
                            f"at {close_ist.strftime('%Y-%m-%d %H:%M')} IST ✓"
                        )
                    except Exception:
                        work_entries = self._reset_and_revalidate_work_entries(employee_id)
                        try:
                            with self.env.cr.savepoint():
                                open_prev.write({
                                    'check_out': close_utc,
                                    'x_studio_no_checkout': True,
                                })
                            _logger.info(
                                f"  → Auto-closed attendance ID {open_prev.id} "
                                f"at {close_ist.strftime('%Y-%m-%d %H:%M')} IST ✓ (after work entry reset)"
                            )
                        except Exception as e2:
                            _logger.warning(f"  → SKIPPED closing attendance ID {open_prev.id} even after reset: {e2}")
                        finally:
                            self._revalidate_work_entries(work_entries)

                has_checkout = len(punches) > 1 and last_punch != first_punch
                first_ist = pytz.UTC.localize(first_punch).astimezone(ist).strftime("%H:%M")
                last_ist = pytz.UTC.localize(last_punch).astimezone(ist).strftime("%H:%M")
                _logger.info(
                    f"  → Creating attendance: check_in={first_ist} "
                    f"check_out={last_ist if has_checkout else 'None'} IST "
                    f"no_checkout={not has_checkout}"
                )
                try:
                    with self.env.cr.savepoint():
                        attendance = HrAttendance.create({
                            'employee_id': employee_id,
                            'check_in': first_punch,
                            'check_out': last_punch if has_checkout else False,
                            'x_studio_no_checkout': not has_checkout,
                        })
                    _logger.info(f"  → Created attendance ID {attendance.id} ✓")
                except Exception:
                    work_entries = self._reset_and_revalidate_work_entries(employee_id)
                    try:
                        with self.env.cr.savepoint():
                            attendance = HrAttendance.create({
                                'employee_id': employee_id,
                                'check_in': first_punch,
                                'check_out': last_punch if has_checkout else False,
                                'x_studio_no_checkout': not has_checkout,
                            })
                        _logger.info(f"  → Created attendance ID {attendance.id} ✓ (after work entry reset)")
                    except Exception as e2:
                        _logger.warning(
                            f"  → SKIPPED creating attendance for Employee {employee_id} on {punch_date} "
                            f"even after work entry reset: {e2}"
                        )
                        self._revalidate_work_entries(work_entries)
                        continue
                    finally:
                        self._revalidate_work_entries(work_entries)

            # -----------------------------------------------
            # CREATE PUNCH LINES
            # -----------------------------------------------
            for p in punches:

                p_ist = pytz.UTC.localize(p["punch_time"]).astimezone(ist).strftime("%H:%M")
                if HrAttendanceLine.search(
                    [('biotime_transaction_id', '=', p["tx_id"])],
                    limit=1
                ):
                    _logger.info(f"  → Punch line tx_id={p['tx_id']} ({p_ist} IST) already exists, skipping")
                    continue
    
                HrAttendanceLine.create({
                    'attendance_id': attendance.id,
                    'employee_id': employee_id,
                    'punch_time': p["punch_time"],
                    'punch_state': False,
                    'terminal_sn': p["terminal_sn"],
                    'terminal_alias': p["terminal_alias"],
                    'biotime_transaction_id': p["tx_id"],
                })
                _logger.info(f"  → Punch line created: tx_id={p['tx_id']} ({p_ist} IST)")

            _logger.info(
                f"  === Done Employee {employee_id} {punch_date} ==="
            )
    
        _logger.info("=== BIOTIME SYNC COMPLETED ===")


    def auto_close_at_nine_pm(self):
    
        _logger = logging.getLogger(__name__)
        _logger.info("=== AUTO CLOSE ATTENDANCE STARTED ===")
    
        HrAttendance = self.env['hr.attendance']
        HrAttendanceLine = self.env['hr.attendance.line']
    
        ist = pytz.timezone("Asia/Kolkata")
    
        now_ist = datetime.now(ist)
        today_ist = now_ist.date()
    
        open_attendances = HrAttendance.search([
            ('check_out', '=', False),
            ('check_in', '!=', False),
        ])
    
        _logger.info(f"Open attendances found: {len(open_attendances)}")
    
        for att in open_attendances:
    
            checkin_utc = fields.Datetime.to_datetime(att.check_in)
            checkin_ist = pytz.UTC.localize(checkin_utc).astimezone(ist)
    
            attendance_date = checkin_ist.date()
    
            # --------------------------------------------------
            # CASE 1: Previous day open → close immediately
            # --------------------------------------------------
            if attendance_date < today_ist:

                _logger.info(f"Closing previous day attendance ID {att.id}")

                day_start = datetime.combine(attendance_date, time(0, 0, 0))
                day_end = datetime.combine(attendance_date, time(23, 59, 59))
                lines = HrAttendanceLine.search([
                    ('employee_id', '=', att.employee_id.id),
                    ('punch_time', '>=', day_start),
                    ('punch_time', '<=', day_end),
                ], order="punch_time asc")

                if lines and len(lines) > 1:
                    # Multiple punches → last punch is checkout
                    checkout_time = lines[-1].punch_time
                    no_checkout_flag = False
                else:
                    # Single punch or no lines → decide by check_in time
                    if checkin_ist.time() < time(19, 0, 0):
                        # Check-in before 7 PM → close at 7 PM
                        close_ist = ist.localize(
                            datetime.combine(attendance_date, time(19, 0, 0))
                        )
                    else:
                        # Check-in at or after 7 PM → close at check_in + 15 min
                        close_ist = checkin_ist + timedelta(minutes=15)
                    checkout_time = close_ist.astimezone(pytz.UTC).replace(tzinfo=None)
                    no_checkout_flag = True

                if checkout_time > att.check_in:
                    try:
                        with self.env.cr.savepoint():
                            att.write({
                                'check_out': checkout_time,
                                'x_studio_no_checkout': no_checkout_flag,
                            })
                        _logger.info(
                            f"Closed attendance {att.id} at {checkout_time}"
                        )
                    except Exception as e:
                        _logger.warning(
                            f"Skipped attendance ID {att.id} (locked by validated work entry): {e}"
                        )

            # --------------------------------------------------
            # CASE 2: Today open AND time > 9 PM → auto close
            # --------------------------------------------------
            elif attendance_date == today_ist:

                if now_ist.time() >= time(19, 0, 0):

                    _logger.info(f"9PM auto close for attendance ID {att.id}")

                    day_start = datetime.combine(attendance_date, time(0, 0, 0))
                    day_end = datetime.combine(attendance_date, time(23, 59, 59))
                    lines = HrAttendanceLine.search([
                        ('employee_id', '=', att.employee_id.id),
                        ('punch_time', '>=', day_start),
                        ('punch_time', '<=', day_end),
                    ], order="punch_time asc")

                    if lines and len(lines) > 1:
                        checkout_time = lines[-1].punch_time
                        no_checkout_flag = False
                    else:
                        if checkin_ist.time() < time(19, 0, 0):
                            close_ist = ist.localize(
                                datetime.combine(attendance_date, time(19, 0, 0))
                            )
                        else:
                            close_ist = checkin_ist + timedelta(minutes=15)
                        checkout_time = close_ist.astimezone(pytz.UTC).replace(tzinfo=None)
                        no_checkout_flag = True

                    if checkout_time > att.check_in:
                        try:
                            with self.env.cr.savepoint():
                                att.write({
                                    'check_out': checkout_time,
                                    'x_studio_no_checkout': no_checkout_flag,
                                })
                            _logger.info(
                                f"11PM closed attendance {att.id}"
                            )
                        except Exception as e:
                            _logger.warning(
                                f"Skipped attendance ID {att.id} (locked by validated work entry): {e}"
                            )
    
        _logger.info("=== AUTO CLOSE ATTENDANCE COMPLETED ===")
    



    def action_sync_terminals(self):
        self.sync_terminals()
        return True
    
    def action_sync_biodata(self):
        self.sync_biodata()
        return True
    
    def action_sync_attendance(self):
        self.sync_attendance()
        return True
    
    def action_manual_close(self):
        self.auto_close_at_nine_pm()
        return True



























