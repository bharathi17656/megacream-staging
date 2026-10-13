from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    delivery_name = fields.Char(string='Recipient / Delivery Name')
    delivery_street = fields.Char(string='Street')
    delivery_street2 = fields.Char(string='Street 2')
    delivery_city = fields.Char(string='City')
    delivery_state_id = fields.Many2one('res.country.state', string='State')
    delivery_zip = fields.Char(string='ZIP / PIN Code')
    delivery_country_id = fields.Many2one('res.country', string='Country')
    delivery_phone = fields.Char(string='Contact No / Phone')
    has_delivery_address = fields.Boolean(
        string='Has Delivery Address',
        compute='_compute_has_delivery_address',
        store=True,
    )

    @api.depends(
        'delivery_name', 'delivery_street', 'delivery_street2',
        'delivery_city', 'delivery_state_id', 'delivery_zip',
        'delivery_country_id', 'delivery_phone'
    )
    def _compute_has_delivery_address(self):
        for move in self:
            move.has_delivery_address = bool(
                move.delivery_name or move.delivery_street or move.delivery_street2
                or move.delivery_city or move.delivery_state_id or move.delivery_zip
                or move.delivery_phone
            )

    def action_copy_customer_address(self):
        self.ensure_one()
        if not self.partner_id:
            return
        partner = self.partner_id
        self.write({
            'delivery_name': partner.name or False,
            'delivery_street': partner.street or False,
            'delivery_street2': partner.street2 or False,
            'delivery_city': partner.city or False,
            'delivery_state_id': partner.state_id.id if partner.state_id else False,
            'delivery_zip': partner.zip or False,
            'delivery_country_id': partner.country_id.id if partner.country_id else False,
            'delivery_phone': partner.phone or partner.mobile or False,
        })

    def action_clear_delivery_address(self):
        self.ensure_one()
        self.write({
            'delivery_name': False,
            'delivery_street': False,
            'delivery_street2': False,
            'delivery_city': False,
            'delivery_state_id': False,
            'delivery_zip': False,
            'delivery_country_id': False,
            'delivery_phone': False,
        })

    def _get_delivery_address_data(self):
        self.ensure_one()
        if self.has_delivery_address:
            return {
                'name': self.delivery_name or '',
                'street': self.delivery_street or '',
                'street2': self.delivery_street2 or '',
                'city': self.delivery_city or '',
                'state': self.delivery_state_id.name if self.delivery_state_id else '',
                'zip': self.delivery_zip or '',
                'country': self.delivery_country_id.name if self.delivery_country_id and self.delivery_country_id != self.company_id.country_id else '',
                'phone': self.delivery_phone or '',
            }
        sale_orders = self.line_ids.sale_line_ids.order_id
        for so in sale_orders:
            if hasattr(so, 'has_delivery_address') and so.has_delivery_address:
                return {
                    'name': so.delivery_name or '',
                    'street': so.delivery_street or '',
                    'street2': so.delivery_street2 or '',
                    'city': so.delivery_city or '',
                    'state': so.delivery_state_id.name if so.delivery_state_id else '',
                    'zip': so.delivery_zip or '',
                    'country': so.delivery_country_id.name if so.delivery_country_id and so.delivery_country_id != self.company_id.country_id else '',
                    'phone': so.delivery_phone or '',
                }
        return False
