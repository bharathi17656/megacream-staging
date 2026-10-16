import calendar
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    def init(self):
        super().init()
        # Automatically update existing Customer Invoices from format MMM/INV/XXX/YY-ZZ to MMM/INV/XXX/YY
        self.env.cr.execute("""
            UPDATE account_move
            SET name = REGEXP_REPLACE(name, '^([A-Z]{3}/INV/[0-9]+/[0-9]{2})-[0-9]{2}$', '\\1')
            WHERE move_type = 'out_invoice'
              AND name ~ '^[A-Z]{3}/INV/[0-9]+/[0-9]{2}-[0-9]{2}$';

            UPDATE account_move
            SET payment_reference = REGEXP_REPLACE(payment_reference, '^([A-Z]{3}/INV/[0-9]+/[0-9]{2})-[0-9]{2}$', '\\1')
            WHERE move_type = 'out_invoice'
              AND payment_reference ~ '^[A-Z]{3}/INV/[0-9]+/[0-9]{2}-[0-9]{2}$';

            UPDATE account_move_line aml
            SET move_name = am.name
            FROM account_move am
            WHERE aml.move_id = am.id
              AND am.move_type = 'out_invoice'
              AND aml.move_name != am.name;
        """)

    def _get_l4e_custom_sequence_name(self, move_type, move_date, company_id=None):
        """
        Generates custom sequence name in format: MMM/TYPE/SEQ/FY
        Example: AUG/INV/001/26 for Customer Invoice
                 AUG/BIL/001/26-27 for Vendor Bill
        - Resets sequence to 001 every month per move_type.
        - Calculates Year as YY (26) for Invoices, and Financial Year YY-(YY+1) (26-27) for Bills.
        """
        if not move_date:
            move_date = fields.Date.context_today(self)

        # 1. Month: 3 uppercase letters (AUG, SEP, JAN, etc.)
        month_str = move_date.strftime('%b').upper()

        # 2. Document type tag: INV for Customer Invoice, BIL for Vendor Bill
        type_tag = 'INV' if move_type == 'out_invoice' else 'BIL'

        # 3. Year: YY (e.g. 26 for year 2026) for Invoice; YY-(YY+1) for Bill
        year_short = move_date.year % 100
        if move_type == 'out_invoice':
            fy_str = f"{year_short:02d}"
        else:
            next_year_short = (year_short + 1) % 100
            fy_str = f"{year_short:02d}-{next_year_short:02d}"

        if not company_id:
            company_id = self.company_id.id if self and self.company_id else self.env.company.id

        # 4. Find max existing sequence number for this prefix in the same month & year
        prefix = f"{month_str}/{type_tag}/"

        domain = [
            ('name', '=like', f"{prefix}%"),
        ]
        if company_id:
            domain.append(('company_id', '=', company_id))
        if self.id:
            domain.append(('id', '!=', self.id))

        moves_in_month = self.sudo().search(domain)

        # Extract sequence numbers matching format .../TYPE/XXX/...
        max_seq = 0
        for m in moves_in_month:
            if m.name and prefix in m.name:
                parts = m.name.split('/')
                if len(parts) >= 3 and parts[2].isdigit():
                    try:
                        num = int(parts[2])
                        if num > max_seq:
                            max_seq = num
                    except ValueError:
                        pass

        next_seq = max_seq + 1
        candidate_name = f"{month_str}/{type_tag}/{next_seq:03d}/{fy_str}"

        # Safety loop: ensure no collision with existing records for this company
        check_domain = [('name', '=', candidate_name)]
        if company_id:
            check_domain.append(('company_id', '=', company_id))
        while self.sudo().search_count(check_domain) > 0:
            next_seq += 1
            candidate_name = f"{month_str}/{type_tag}/{next_seq:03d}/{fy_str}"
            check_domain[0] = ('name', '=', candidate_name)

        return candidate_name

    def action_post(self):
        for move in self:
            if move.move_type in ('out_invoice', 'in_invoice'):
                if not move.name or move.name == '/' or move.state == 'draft':
                    move_date = move.invoice_date or move.date or fields.Date.context_today(move)
                    new_name = move._get_l4e_custom_sequence_name(move.move_type, move_date, company_id=move.company_id.id)
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
                fy_str = f"{year_short:02d}"
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
