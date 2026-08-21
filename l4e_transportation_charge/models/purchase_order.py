from odoo import api, fields, models


def _is_exempt_tax_group(group):
    """A tax_totals tax_group dict is considered 'Exempt' if its name/label
    mentions exempt (e.g. a 0% Exempt tax). Used to detect and hide these
    zero-value rows from the totals breakdown widget."""
    return 'exempt' in (group.get('group_name') or '').lower() or \
           'exempt' in (group.get('group_label') or '').lower()


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    transport_charge_amount = fields.Monetary(string='Transport Charge', default=0.0)
    transport_charge_tax_percent = fields.Float(string='Transport Charge Tax %', default=0.0)
    transport_charge_tax_amount = fields.Monetary(string='Transport Charge Tax', default=0.0)

    @api.depends('transport_charge_amount', 'transport_charge_tax_amount')
    def _amount_all(self):
        super()._amount_all()
        for order in self:
            transport = order.transport_charge_amount + order.transport_charge_tax_amount
            if transport:
                order.amount_total += transport
                order.amount_total_cc += transport

    def _hide_exempt_tax_groups(self):
        """Remove 'Exempt' tax groups (e.g. 0% Exempt) from the tax_totals
        breakdown so they don't render as a zero-value line in the totals
        widget. This is purely cosmetic: the group's tax_amount is always
        0.00, so Untaxed Amount / Total are unaffected by removing it."""
        self.ensure_one()
        totals = self.tax_totals
        subtotals = totals and totals.get('subtotals')
        if not subtotals:
            return
        changed = False
        for subtotal in subtotals:
            tax_groups = subtotal.get('tax_groups') or []
            filtered = [g for g in tax_groups if not _is_exempt_tax_group(g)]
            if len(filtered) != len(tax_groups):
                subtotal['tax_groups'] = filtered
                changed = True
        if changed:
            totals['subtotals'] = subtotals
            self.tax_totals = totals

    @api.depends('transport_charge_amount', 'transport_charge_tax_amount')
    def _compute_tax_totals(self):
        super()._compute_tax_totals()
        for order in self:
            order._hide_exempt_tax_groups()

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

            if transport_tax:
                eligible_count = sum(1 for g in tax_groups if not _is_exempt_tax_group(g))
                if eligible_count:
                    allocated = 0.0
                    seen = 0
                    merged_groups = []
                    for group in tax_groups:
                        if _is_exempt_tax_group(group):
                            merged_groups.append(group)
                            continue
                        group = dict(group)
                        seen += 1
                        if seen == eligible_count:
                            share = transport_tax - allocated
                        else:
                            share = transport_tax / eligible_count
                            allocated += share
                        group['tax_amount_currency'] = group.get('tax_amount_currency', 0.0) + share
                        group['tax_amount'] = group.get('tax_amount', 0.0) + share
                        merged_groups.append(group)
                    tax_groups = merged_groups
                else:
                    tax_groups.insert(0, {
                        'id': False, 'group_name': 'Transport Tax', 'group_label': 'Transport Tax',
                        'involved_tax_ids': [], 'base_amount_currency': 0.0, 'base_amount': 0.0,
                        'tax_amount_currency': transport_tax, 'tax_amount': transport_tax,
                        'display_base_amount_currency': 0.0, 'display_base_amount': 0.0,
                    })

            if transport:
                tax_groups.insert(0, {
                    'id': False, 'group_name': 'Transport', 'group_label': 'Transport',
                    'involved_tax_ids': [], 'base_amount_currency': 0.0, 'base_amount': 0.0,
                    'tax_amount_currency': transport, 'tax_amount': transport,
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
                'default_tax_amount_percent': self.transport_charge_tax_percent,
            },
        }
        
    def action_create_invoice(self):
        result = super().action_create_invoice()
        for order in self:
            transport = order.transport_charge_amount
            transport_tax = order.transport_charge_tax_amount
            if not transport and not transport_tax:
                continue

            bills = self.env['account.move'].search([
                ('invoice_origin', '=', order.name),
                ('move_type', '=', 'in_invoice'),
            ])
            for move in bills:
                if move.state != 'draft':
                    continue
                account = move.invoice_line_ids[:1].account_id or move.journal_id.default_account_id
                if not account:
                    continue

                lines_vals = []
                if transport:
                    lines_vals.append((0, 0, {
                        'name': 'Transport',
                        'account_id': account.id,
                        'quantity': 1,
                        'price_unit': transport,
                        'tax_ids': [(6, 0, [])],
                    }))
                if transport_tax:
                    lines_vals.append((0, 0, {
                        'name': 'Transport Tax',
                        'account_id': account.id,
                        'quantity': 1,
                        'price_unit': transport_tax,
                        'tax_ids': [(6, 0, [])],
                    }))
                if lines_vals:
                    move.write({'invoice_line_ids': lines_vals})
        return result