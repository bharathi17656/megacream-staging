from odoo import api, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.onchange('purchase_id')
    def _onchange_purchase_id_add_transport_charge(self):
        order = self.purchase_id
        if not order:
            return

        transport = order.transport_charge_amount
        transport_tax = order.transport_charge_tax_amount
        if not transport and not transport_tax:
            return

        existing_names = self.invoice_line_ids.mapped('name')
        account = self.invoice_line_ids[:1].account_id or self.journal_id.default_account_id
        AccountMoveLine = self.env['account.move.line']

        if transport and 'Transport' not in existing_names:
            self.invoice_line_ids += AccountMoveLine.new({
                'name': 'Transport',
                'account_id': account.id if account else False,
                'quantity': 1,
                'price_unit': transport,
                'tax_ids': [(6, 0, [])],
            })
        if transport_tax and 'Transport Tax' not in existing_names:
            self.invoice_line_ids += AccountMoveLine.new({
                'name': 'Transport Tax',
                'account_id': account.id if account else False,
                'quantity': 1,
                'price_unit': transport_tax,
                'tax_ids': [(6, 0, [])],
            })