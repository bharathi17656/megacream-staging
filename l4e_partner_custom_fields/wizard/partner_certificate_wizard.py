from odoo import fields, models, _


class PartnerCertificateWizard(models.TransientModel):
    _name = 'partner.certificate.wizard'
    _description = 'Partner Certificate Wizard'

    partner_id = fields.Many2one('res.partner', string='Contact', required=True)
    name = fields.Char(string='Certificate Name', required=True)
    certificate_file = fields.Binary(string='Certificate File', required=True)
    file_name = fields.Char(string='File Name')
    expiry_date = fields.Date(string='Expiration Date')

    def action_save(self):
        self.ensure_one()
        file_name = self.file_name or (f"{self.name}.pdf" if self.name else "certificate.pdf")
        self.env['res.partner.certificate'].create({
            'partner_id': self.partner_id.id,
            'name': self.name,
            'certificate_file': self.certificate_file,
            'file_name': file_name,
            'expiry_date': self.expiry_date,
        })
        return {'type': 'ir.actions.act_window_close'}
