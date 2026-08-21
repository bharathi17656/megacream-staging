from odoo import api, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            move._l4e_add_transport_charge_lines()
        return moves

    def _l4e_add_transport_charge_lines(self):
        self.ensure_one()
        if self.move_type != 'in_invoice' or not self.invoice_origin:
            return

        order = self.env['purchase.order'].search([('name', '=', self.invoice_origin)], limit=1)
        if not order:
            return

        transport = order.transport_charge_amount
        transport_tax = order.transport_charge_tax_amount
        if not transport and not transport_tax:
            return

        existing_names = self.invoice_line_ids.mapped('name')
        account = self.invoice_line_ids[:1].account_id or self.journal_id.default_account_id

        lines_vals = []
        if transport and 'Transport' not in existing_names:
            lines_vals.append((0, 0, {
                'name': 'Transport',
                'account_id': account.id if account else False,
                'quantity': 1,
                'price_unit': transport,
                'tax_ids': [(6, 0, [])],
            }))
        if transport_tax and 'Transport Tax' not in existing_names:
            lines_vals.append((0, 0, {
                'name': 'Transport Tax',
                'account_id': account.id if account else False,
                'quantity': 1,
                'price_unit': transport_tax,
                'tax_ids': [(6, 0, [])],
            }))
        if lines_vals:
            self.write({'invoice_line_ids': lines_vals})