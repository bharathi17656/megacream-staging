from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

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
        for order in self:
            order.has_delivery_address = bool(
                order.delivery_name or order.delivery_street or order.delivery_street2
                or order.delivery_city or order.delivery_state_id or order.delivery_zip
                or order.delivery_phone
            )

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        invoice_vals.update({
            'delivery_name': self.delivery_name,
            'delivery_street': self.delivery_street,
            'delivery_street2': self.delivery_street2,
            'delivery_city': self.delivery_city,
            'delivery_state_id': self.delivery_state_id.id if self.delivery_state_id else False,
            'delivery_zip': self.delivery_zip,
            'delivery_country_id': self.delivery_country_id.id if self.delivery_country_id else False,
            'delivery_phone': self.delivery_phone,
        })
        return invoice_vals

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
        return False
