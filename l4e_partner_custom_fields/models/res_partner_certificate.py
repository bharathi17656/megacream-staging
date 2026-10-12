from odoo import fields, models


class ResPartnerCertificate(models.Model):
    _name = 'res.partner.certificate'
    _description = 'Partner Certificate'
    _order = 'expiry_date asc, id desc'

    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        required=True,
        ondelete='cascade',
        index=True
    )
    name = fields.Char(string='Certificate Name', required=True)
    certificate_file = fields.Binary(string='Certificate File', required=True, attachment=True)
    file_name = fields.Char(string='File Name')
    expiry_date = fields.Date(string='Expiration Date')
