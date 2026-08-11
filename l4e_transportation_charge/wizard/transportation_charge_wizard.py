from odoo import fields, models


class TransportationChargeWizard(models.TransientModel):
    _name = 'transportation.charge.wizard'
    _description = 'Transportation Charge Wizard'

    sale_order_id = fields.Many2one('sale.order')
    purchase_order_id = fields.Many2one('purchase.order')
    amount = fields.Float(string='Amount')
    tax_amount = fields.Float(string='Tax Amount')

    def action_apply(self):
        self.ensure_one()
        order = self.sale_order_id or self.purchase_order_id
        order.write({
            'transport_charge_amount': self.amount,
            'transport_charge_tax_amount': self.tax_amount,
        })
        return {'type': 'ir.actions.act_window_close'}