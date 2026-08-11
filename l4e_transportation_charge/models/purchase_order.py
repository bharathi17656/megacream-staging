from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    transport_charge_amount = fields.Monetary(string='Transport Charge', default=0.0)
    transport_charge_tax_amount = fields.Monetary(string='Transport Charge Tax', default=0.0)

    @api.depends('transport_charge_amount', 'transport_charge_tax_amount')
    def _amount_all(self):
        super()._amount_all()
        for order in self:
            transport = order.transport_charge_amount + order.transport_charge_tax_amount
            if transport:
                order.amount_total += transport
                order.amount_total_cc += transport

    @api.depends('transport_charge_amount', 'transport_charge_tax_amount')
    def _compute_tax_totals(self):
        super()._compute_tax_totals()
        for order in self:
            transport = order.transport_charge_amount
            transport_tax = order.transport_charge_tax_amount
            if not transport and not transport_tax:
                continue
            totals = order.tax_totals
            subtotals = totals and totals.get('subtotals')
            if not subtotals:
                continue

            first = subtotals[0]
            tax_groups = list(first.get('tax_groups') or [])
            if transport:
                tax_groups.append({
                    'id': False, 'group_name': 'Transport', 'group_label': 'Transport',
                    'involved_tax_ids': [], 'base_amount_currency': 0.0, 'base_amount': 0.0,
                    'tax_amount_currency': transport, 'tax_amount': transport,
                    'display_base_amount_currency': 0.0, 'display_base_amount': 0.0,
                })
            if transport_tax:
                tax_groups.append({
                    'id': False, 'group_name': 'Transport Tax', 'group_label': 'Transport Tax',
                    'involved_tax_ids': [], 'base_amount_currency': 0.0, 'base_amount': 0.0,
                    'tax_amount_currency': transport_tax, 'tax_amount': transport_tax,
                    'display_base_amount_currency': 0.0, 'display_base_amount': 0.0,
                })
            first['tax_groups'] = tax_groups
            subtotals[0] = first
            totals['subtotals'] = subtotals

            combined = transport + transport_tax
            for key in ('tax_amount_currency', 'tax_amount', 'total_amount_currency', 'total_amount'):
                totals[key] = totals.get(key, 0.0) + combined
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
                'default_purchase_order_id': self.id,
                'default_amount': self.transport_charge_amount,
                'default_tax_amount': self.transport_charge_tax_amount,
            },
        }