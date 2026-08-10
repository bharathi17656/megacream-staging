import calendar
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _get_l4e_custom_sequence_name(self, order_date):
        """
        Generates custom sequence name in format: MMM/PO/SEQ/FY
        Example: AUG/PO/001/26-27
        """
        if not order_date:
            order_date = fields.Date.context_today(self)

        month_str = order_date.strftime('%b').upper()
        type_tag = 'PO'
        year_short = order_date.year % 100
        next_year_short = (year_short + 1) % 100
        fy_str = f"{year_short:02d}-{next_year_short:02d}"

        last_day_num = calendar.monthrange(order_date.year, order_date.month)[1]
        start_date = order_date.replace(day=1)
        end_date = order_date.replace(day=last_day_num)

        domain = [
            ('date_order', '>=', start_date),
            ('date_order', '<=', end_date),
            ('name', '!=', False),
            ('name', '!=', '/'),
            ('name', '!=', 'New'),
        ]
        if self.id:
            domain.append(('id', '!=', self.id))

        orders_in_month = self.sudo().search(domain)

        max_seq = 0
        tag_pattern = f"/{type_tag}/"
        for p in orders_in_month:
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
            if not vals.get('name') or vals.get('name') in ('/', 'New') or vals.get('name', '').startswith('P0'):
                order_date = fields.Date.today()
                if vals.get('date_order'):
                    order_date = fields.Date.to_date(vals['date_order'])
                vals['name'] = self._get_l4e_custom_sequence_name(order_date)
        return super().create(vals_list)

    def button_confirm(self):
        res = super().button_confirm()
        for order in self:
            if not order.name or order.name in ('/', 'New') or not ('/PO/' in order.name):
                order_date = fields.Date.to_date(order.date_order) if order.date_order else fields.Date.today()
                order.name = order._get_l4e_custom_sequence_name(order_date)
        return res

    @api.model
    def cron_update_old_purchase_orders(self):
        """
        Cron Function: Update names of old Purchase Orders sequentially.
        """
        _logger.info("L4E: Starting update of old Purchase Order names...")
        orders = self.search([], order='date_order asc, id asc')

        grouped = {}
        for order in orders:
            order_date = fields.Date.to_date(order.date_order) if order.date_order else fields.Date.today()
            key = (order_date.year, order_date.month)
            grouped.setdefault(key, []).append(order)

        count = 0
        for (year, month), order_list in grouped.items():
            seq = 1
            for order in order_list:
                order_date = fields.Date.to_date(order.date_order) if order.date_order else fields.Date.today()
                month_str = order_date.strftime('%b').upper()
                year_short = order_date.year % 100
                next_year_short = (year_short + 1) % 100
                fy_str = f"{year_short:02d}-{next_year_short:02d}"
                seq_str = f"{seq:03d}"
                new_name = f"{month_str}/PO/{seq_str}/{fy_str}"

                if order.name != new_name:
                    order.sudo().write({'name': new_name})
                    count += 1
                seq += 1

        _logger.info(f"L4E: Finished update of old Purchase Orders. Updated {count} records.")
        return True
