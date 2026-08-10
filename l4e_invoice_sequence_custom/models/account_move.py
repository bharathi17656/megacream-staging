import calendar
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_l4e_custom_sequence_name(self, move_type, move_date):
        """
        Generates custom sequence name in format: MMM/TYPE/SEQ/FY
        Example: AUG/INV/001/26-27 for Customer Invoice
                 AUG/BIL/001/26-27 for Vendor Bill
        - Resets sequence to 001 every month per move_type.
        - Calculates Financial Year as YY-(YY+1) (e.g., 2026 -> 26-27).
        """
        if not move_date:
            move_date = fields.Date.context_today(self)

        # 1. Month: 3 uppercase letters (AUG, SEP, JAN, etc.)
        month_str = move_date.strftime('%b').upper()

        # 2. Document type tag: INV for Customer Invoice, BIL for Vendor Bill
        type_tag = 'INV' if move_type == 'out_invoice' else 'BIL'

        # 3. Financial Year: YY-(YY+1) e.g. 26-27 for year 2026
        year_short = move_date.year % 100
        next_year_short = (year_short + 1) % 100
        fy_str = f"{year_short:02d}-{next_year_short:02d}"

        # 4. Find max existing sequence number for this move_type in the same month & year
        last_day_num = calendar.monthrange(move_date.year, move_date.month)[1]
        start_date = move_date.replace(day=1)
        end_date = move_date.replace(day=last_day_num)

        domain = [
            ('move_type', '=', move_type),
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('name', '!=', False),
            ('name', '!=', '/'),
        ]
        if self.id:
            domain.append(('id', '!=', self.id))

        moves_in_month = self.sudo().search(domain)

        # Extract sequence numbers matching format .../TYPE/XXX/...
        max_seq = 0
        tag_pattern = f"/{type_tag}/"
        for m in moves_in_month:
            if m.name and tag_pattern in m.name:
                parts = m.name.split('/')
                for part in parts:
                    if part.isdigit() and len(part) == 3:
                        try:
                            num = int(part)
                            if num > max_seq:
                                max_seq = num
                        except ValueError:
                            pass

        next_seq = max_seq + 1
        seq_str = f"{next_seq:03d}"

        return f"{month_str}/{type_tag}/{seq_str}/{fy_str}"

    def action_post(self):
        for move in self:
            if move.move_type in ('out_invoice', 'in_invoice'):
                if not move.name or move.name == '/' or move.state == 'draft':
                    move_date = move.invoice_date or move.date or fields.Date.context_today(move)
                    new_name = move._get_l4e_custom_sequence_name(move.move_type, move_date)
                    move.name = new_name
        return super().action_post()

    @api.depends('journal_id', 'sequence_number', 'sequence_prefix', 'state')
    def _compute_made_sequence_gap(self):
        super()._compute_made_sequence_gap()
        for move in self:
            if move.move_type in ('out_invoice', 'in_invoice') and move.name and move.name != '/':
                move.made_sequence_gap = False

    @api.model
    def cron_update_old_invoices(self):
        """
        Cron Function 1: Update names of old Customer Invoices (out_invoice) sequentially.
        """
        _logger.info("L4E: Starting update of old Customer Invoice names...")
        invoices = self.search([('move_type', '=', 'out_invoice')], order='date asc, id asc')

        grouped = {}
        for inv in invoices:
            inv_date = inv.invoice_date or inv.date or fields.Date.today()
            key = (inv_date.year, inv_date.month)
            grouped.setdefault(key, []).append(inv)

        count = 0
        for (year, month), inv_list in grouped.items():
            seq = 1
            for inv in inv_list:
                inv_date = inv.invoice_date or inv.date or fields.Date.today()
                month_str = inv_date.strftime('%b').upper()
                year_short = inv_date.year % 100
                next_year_short = (year_short + 1) % 100
                fy_str = f"{year_short:02d}-{next_year_short:02d}"
                seq_str = f"{seq:03d}"
                new_name = f"{month_str}/INV/{seq_str}/{fy_str}"

                if inv.name != new_name:
                    inv.sudo().write({'name': new_name, 'made_sequence_gap': False})
                    count += 1
                seq += 1

        _logger.info(f"L4E: Finished update of old Customer Invoices. Updated {count} records.")
        return True

    @api.model
    def cron_update_old_bills(self):
        """
        Cron Function 2: Update names of old Vendor Bills (in_invoice) sequentially.
        """
        _logger.info("L4E: Starting update of old Vendor Bill names...")
        bills = self.search([('move_type', '=', 'in_invoice')], order='date asc, id asc')

        grouped = {}
        for bill in bills:
            bill_date = bill.invoice_date or bill.date or fields.Date.today()
            key = (bill_date.year, bill_date.month)
            grouped.setdefault(key, []).append(bill)

        count = 0
        for (year, month), bill_list in grouped.items():
            seq = 1
            for bill in bill_list:
                bill_date = bill.invoice_date or bill.date or fields.Date.today()
                month_str = bill_date.strftime('%b').upper()
                year_short = bill_date.year % 100
                next_year_short = (year_short + 1) % 100
                fy_str = f"{year_short:02d}-{next_year_short:02d}"
                seq_str = f"{seq:03d}"
                new_name = f"{month_str}/BIL/{seq_str}/{fy_str}"

                if bill.name != new_name:
                    bill.sudo().write({'name': new_name, 'made_sequence_gap': False})
                    count += 1
                seq += 1

        _logger.info(f"L4E: Finished update of old Vendor Bills. Updated {count} records.")
        return True
