from odoo import api, fields, models
from odoo.tools import formatLang


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    transport_charge_amount = fields.Monetary(string='Transport Charge', default=0.0)
    transport_charge_tax_amount = fields.Monetary(string='Transport Charge Tax', default=0.0)

    @api.depends('transport_charge_amount', 'transport_charge_tax_amount')
    def _compute_amounts(self):
        super()._compute_amounts()
        for order in self:
            transport = order.transport_charge_amount + order.transport_charge_tax_amount
            if transport:
                order.amount_total += transport

    @api.depends('transport_charge_amount', 'transport_charge_tax_amount')
    def _compute_tax_totals(self):
        super()._compute_tax_totals()
        for order in self:
            if not order.transport_charge_amount and not order.transport_charge_tax_amount:
                continue
            totals = dict(order.tax_totals or {})
            subtotals = list(totals.get('subtotals') or [])
            if subtotals:
                first = dict(subtotals[0])
                tax_groups = list(first.get('tax_groups') or [])
                if order.transport_charge_amount:
                    tax_groups.append({
                        'group_name': 'Transport',
                        'group_key': 'transport_charge',
                        'tax_group_amount': order.transport_charge_amount,
                        'formatted_tax_group_amount': formatLang(
                            self.env, order.transport_charge_amount, currency_obj=order.currency_id),
                    })
                if order.transport_charge_tax_amount:
                    tax_groups.append({
                        'group_name': 'Transport Tax',
                        'group_key': 'transport_charge_tax',
                        'tax_group_amount': order.transport_charge_tax_amount,
                        'formatted_tax_group_amount': formatLang(
                            self.env, order.transport_charge_tax_amount, currency_obj=order.currency_id),
                    })
                first['tax_groups'] = tax_groups
                subtotals[0] = first
                totals['subtotals'] = subtotals
            totals['amount_total'] = order.amount_total
            totals['formatted_amount_total'] = formatLang(
                self.env, order.amount_total, currency_obj=order.currency_id)
            order.tax_totals = totals

    def action_open_transportation_charge_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Transportation Charge',
            'res_model': 'transportation.charge.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'default_amount': self.transport_charge_amount,
                'default_tax_amount': self.transport_charge_tax_amount,
            },
        }