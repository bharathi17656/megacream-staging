from odoo import fields, models


class DryIcePackingWizard(models.TransientModel):
    _name = 'dry.ice.packing.wizard'
    _description = 'Dry Ice Packing Charge Wizard'

    sale_order_id = fields.Many2one('sale.order')
    amount = fields.Float(string='Amount')
    qty = fields.Float(string='Qty')

    def action_apply(self):
        self.ensure_one()
        self.sale_order_id.write({
            'dry_ice_packing_amount': self.amount,
            'dry_ice_packing_qty': self.qty,
        })
        return {'type': 'ir.actions.act_window_close'}
