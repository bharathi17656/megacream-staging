from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    dry_ice_packing_amount = fields.Monetary(string='Dry Ice Packing Charge', default=0.0)
    dry_ice_packing_qty = fields.Float(string='Dry Ice Packing Qty', default=0.0)

    @api.depends('dry_ice_packing_amount')
    def _compute_amounts(self):
        super()._compute_amounts()
        for order in self:
            if order.dry_ice_packing_amount:
                order.amount_total += order.dry_ice_packing_amount

    @api.depends('dry_ice_packing_amount')
    def _compute_tax_totals(self):
        super()._compute_tax_totals()
        for order in self:
            charge = order.dry_ice_packing_amount
            if not charge:
                continue
            totals = order.tax_totals
            subtotals = totals and totals.get('subtotals')
            if not subtotals:
                continue

            first = subtotals[0]
            tax_groups = list(first.get('tax_groups') or [])
            tax_groups.insert(0, {
                'id': False, 'group_name': 'Dry ice packing charge', 'group_label': 'Dry ice packing charge',
                'involved_tax_ids': [], 'base_amount_currency': 0.0, 'base_amount': 0.0,
                'tax_amount_currency': charge, 'tax_amount': charge,
                'display_base_amount_currency': 0.0, 'display_base_amount': 0.0,
            })
            first['tax_groups'] = tax_groups
            subtotals[0] = first
            totals['subtotals'] = subtotals

            for key in ('tax_amount_currency', 'tax_amount', 'total_amount_currency', 'total_amount'):
                totals[key] = totals.get(key, 0.0) + charge
            order.tax_totals = totals

    def action_open_dry_ice_packing_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dry Ice Packing Charge',
            'res_model': 'dry.ice.packing.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'default_amount': self.dry_ice_packing_amount,
                'default_qty': self.dry_ice_packing_qty,
            },
        }

    def _create_invoices(self, grouped=False, final=False, date=None):
        moves = super()._create_invoices(grouped=grouped, final=final, date=date)
        for order in self:
            charge = order.dry_ice_packing_amount
            if not charge:
                continue

            order_moves = moves.filtered(lambda m: order in m.line_ids.sale_line_ids.order_id)
            for move in order_moves:
                if move.state != 'draft':
                    continue
                account = move.invoice_line_ids[:1].account_id or move.journal_id.default_account_id
                if not account:
                    continue

                qty_note = f' (Qty: {order.dry_ice_packing_qty})' if order.dry_ice_packing_qty else ''
                move.write({'invoice_line_ids': [(0, 0, {
                    'name': f'Dry ice packing charge{qty_note}',
                    'account_id': account.id,
                    'quantity': 1,
                    'price_unit': charge,
                    'tax_ids': [(6, 0, [])],
                })]})
        return moves
