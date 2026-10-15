import calendar
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_l4e_custom_sequence_name(self, order_date, company_id=None):
        """
        Generates custom sequence name in format: MMM/SO/SEQ/FY
        Example: AUG/SO/001/26-27
        """
        if not order_date:
            order_date = fields.Date.context_today(self)

        month_str = order_date.strftime('%b').upper()
        type_tag = 'SO'
        year_short = order_date.year % 100
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

        orders_in_month = self.sudo().search(domain)

        max_seq = 0
        for o in orders_in_month:
            if o.name and prefix in o.name:
                parts = o.name.split('/')
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
            if not vals.get('name') or vals.get('name') in ('/', 'New'):
                order_date = fields.Date.today()
                if vals.get('date_order'):
                    order_date = fields.Date.to_date(vals['date_order'])
                cid = vals.get('company_id') or self.env.company.id
                vals['name'] = self._get_l4e_custom_sequence_name(order_date, company_id=cid)
        return super().create(vals_list)

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            if not order.name or order.name in ('/', 'New') or not ('/SO/' in order.name):
                order_date = fields.Date.to_date(order.date_order) if order.date_order else fields.Date.today()
                order.name = order._get_l4e_custom_sequence_name(order_date, company_id=order.company_id.id)
        return res

    @api.model
    def cron_update_old_sale_orders(self):
        """
        Cron Function: Update names of old Sale Orders sequentially.
        """
        _logger.info("L4E: Starting update of old Sale Order names...")
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
                new_name = f"{month_str}/SO/{seq_str}/{fy_str}"

                if order.name != new_name:
                    order.sudo().write({'name': new_name})
                    count += 1
                seq += 1

        _logger.info(f"L4E: Finished update of old Sale Orders. Updated {count} records.")
        return True
