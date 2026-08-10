import calendar
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_l4e_custom_sequence_name(self, picking_date):
        """
        Generates custom sequence name in format: MMM/DO/SEQ/FY
        Example: AUG/DO/001/26-27 for Delivery Orders
        """
        if not picking_date:
            picking_date = fields.Date.context_today(self)

        month_str = picking_date.strftime('%b').upper()
        type_tag = 'DO'
        year_short = picking_date.year % 100
        next_year_short = (year_short + 1) % 100
        fy_str = f"{year_short:02d}-{next_year_short:02d}"

        last_day_num = calendar.monthrange(picking_date.year, picking_date.month)[1]
        start_date = picking_date.replace(day=1)
        end_date = picking_date.replace(day=last_day_num)

        domain = [
            ('scheduled_date', '>=', start_date),
            ('scheduled_date', '<=', end_date),
            ('name', '!=', False),
            ('name', '!=', '/'),
            ('name', '!=', 'New'),
        ]
        if self.id:
            domain.append(('id', '!=', self.id))

        pickings_in_month = self.sudo().search(domain)

        max_seq = 0
        tag_pattern = f"/{type_tag}/"
        for p in pickings_in_month:
            if p.name and tag_pattern in p.name:
                parts = p.name.split('/')
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            picking_type = self.env['stock.picking.type'].browse(vals.get('picking_type_id')) if vals.get('picking_type_id') else False
            is_outgoing = picking_type and picking_type.code == 'outgoing'
            if is_outgoing and (not vals.get('name') or vals.get('name') in ('/', 'New') or 'OUT' in vals.get('name', '')):
                p_date = fields.Date.today()
                if vals.get('scheduled_date'):
                    p_date = fields.Date.to_date(vals['scheduled_date'])
                vals['name'] = self._get_l4e_custom_sequence_name(p_date)
        return super().create(vals_list)

    def action_confirm(self):
        res = super().action_confirm()
        for picking in self:
            if picking.picking_type_code == 'outgoing':
                if not picking.name or picking.name in ('/', 'New') or not ('/DO/' in picking.name):
                    p_date = fields.Date.to_date(picking.scheduled_date) if picking.scheduled_date else fields.Date.today()
                    picking.name = picking._get_l4e_custom_sequence_name(p_date)
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
