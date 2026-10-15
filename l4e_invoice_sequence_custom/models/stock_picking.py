import calendar
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_l4e_custom_sequence_name(self, picking_type_code, picking_date, company_id=None):
        """
        Generates custom sequence name in format: MMM/TYPE/SEQ/FY
        Example: AUG/GRN/001/26-27 for Receipts (incoming)
                 AUG/DO/001/26-27 for Delivery Orders (outgoing)
        """
        if not picking_date:
            picking_date = fields.Date.context_today(self)

        month_str = picking_date.strftime('%b').upper()
        type_tag = 'GRN' if picking_type_code == 'incoming' else 'DO'
        year_short = picking_date.year % 100
        next_year_short = (year_short + 1) % 100
        fy_str = f"{year_short:02d}-{next_year_short:02d}"

        if not company_id:
            company_id = self.company_id.id if self and self.company_id else self.env.company.id

        prefix = f"{month_str}/{type_tag}/"

        domain = [
            ('name', '=like', f"{prefix}%"),
        ]
        if company_id:
            domain.append(('company_id', '=', company_id))
        if self.id:
            domain.append(('id', '!=', self.id))

        existing_pickings = self.sudo().search(domain)

        max_seq = 0
        for p in existing_pickings:
            if p.name and prefix in p.name:
                parts = p.name.split('/')
                # Expecting format: [MONTH, TYPE, SEQ, FY]
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            picking_type = self.env['stock.picking.type'].browse(vals.get('picking_type_id')) if vals.get('picking_type_id') else False
            p_code = picking_type.code if picking_type else False
            if p_code in ('incoming', 'outgoing') and (not vals.get('name') or vals.get('name') in ('/', 'New') or 'IN' in vals.get('name', '') or 'OUT' in vals.get('name', '')):
                p_date = fields.Date.today()
                if vals.get('scheduled_date'):
                    p_date = fields.Date.to_date(vals['scheduled_date'])
                elif vals.get('date'):
                    p_date = fields.Date.to_date(vals['date'])
                cid = vals.get('company_id') or self.env.company.id
                vals['name'] = self._get_l4e_custom_sequence_name(p_code, p_date, company_id=cid)
        return super().create(vals_list)

    def action_confirm(self):
        res = super().action_confirm()
        for picking in self:
            if picking.picking_type_code in ('incoming', 'outgoing'):
                tag = '/GRN/' if picking.picking_type_code == 'incoming' else '/DO/'
                if not picking.name or picking.name in ('/', 'New') or not (tag in picking.name):
                    p_date = fields.Date.to_date(picking.scheduled_date) if picking.scheduled_date else (fields.Date.to_date(picking.date) if picking.date else fields.Date.today())
                    picking.name = picking._get_l4e_custom_sequence_name(picking.picking_type_code, p_date, company_id=picking.company_id.id)
        return res

    @api.model
    def cron_update_old_delivery_orders(self):
        """
        Cron Function: Update names of old Delivery Orders (outgoing pickings) sequentially.
        """
        _logger.info("L4E: Starting update of old Delivery Order names...")
        pickings = self.search([('picking_type_code', '=', 'outgoing')], order='scheduled_date asc, id asc')

        grouped = {}
        for p in pickings:
            p_date = fields.Date.to_date(p.scheduled_date) if p.scheduled_date else fields.Date.today()
            key = (p_date.year, p_date.month)
            grouped.setdefault(key, []).append(p)

        count = 0
        for (year, month), p_list in grouped.items():
            seq = 1
            for p in p_list:
                p_date = fields.Date.to_date(p.scheduled_date) if p.scheduled_date else fields.Date.today()
                month_str = p_date.strftime('%b').upper()
                year_short = p_date.year % 100
                next_year_short = (year_short + 1) % 100
                fy_str = f"{year_short:02d}-{next_year_short:02d}"
                seq_str = f"{seq:03d}"
                new_name = f"{month_str}/DO/{seq_str}/{fy_str}"

                if p.name != new_name:
                    p.sudo().write({'name': new_name})
                    count += 1
                seq += 1

        _logger.info(f"L4E: Finished update of old Delivery Orders. Updated {count} records.")
        return True

    @api.model
    def cron_update_old_receipts(self):
        """
        Cron Function: Update names of old Receipts (incoming pickings) sequentially.
        """
        _logger.info("L4E: Starting update of old Receipt (GRN) names...")
        pickings = self.search([('picking_type_code', '=', 'incoming')], order='scheduled_date asc, id asc')

        grouped = {}
        for p in pickings:
            p_date = fields.Date.to_date(p.scheduled_date) if p.scheduled_date else fields.Date.today()
            key = (p_date.year, p_date.month)
            grouped.setdefault(key, []).append(p)

        count = 0
        for (year, month), p_list in grouped.items():
            seq = 1
            for p in p_list:
                p_date = fields.Date.to_date(p.scheduled_date) if p.scheduled_date else fields.Date.today()
                month_str = p_date.strftime('%b').upper()
                year_short = p_date.year % 100
                next_year_short = (year_short + 1) % 100
                fy_str = f"{year_short:02d}-{next_year_short:02d}"
                seq_str = f"{seq:03d}"
                new_name = f"{month_str}/GRN/{seq_str}/{fy_str}"

                if p.name != new_name:
                    p.sudo().write({'name': new_name})
                    count += 1
                seq += 1

        _logger.info(f"L4E: Finished update of old Receipts. Updated {count} records.")
        return True
