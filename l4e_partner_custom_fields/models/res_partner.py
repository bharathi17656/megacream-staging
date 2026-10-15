from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_vendor = fields.Boolean(
        string='Vendor',
        default=False,
        help="Check this box if this contact is a vendor."
    )
    is_customer = fields.Boolean(
        string='Customer',
        default=False,
        help="Check this box if this contact is a customer."
    )
    certificate_ids = fields.One2many(
        'res.partner.certificate',
        'partner_id',
        string='Certificates',
        help="Uploaded certificates for this contact."
    )
    fssai_no = fields.Char(
        string='FSSAI',
        size=14,
        help="14-digit FSSAI License/Registration Number."
    )
    accounts_contact_number = fields.Char(
        string="Accounts Contact Number",
    )
    accounts_name = fields.Char(
        string="Accounts Name",
    )
    salesperson_name = fields.Char(
        string="Salesperson Name",
    )
    sales_contact_number = fields.Char(
        string="Sales Contact Number",
    )
    store_person_name = fields.Char(
        string="Store Person Name",
    )
    store_person_number = fields.Char(
        string="Store Person Number",
    )

    @api.constrains('fssai_no')
    def _check_fssai_no(self):
        for record in self:
            if record.fssai_no:
                if not record.fssai_no.isdigit() or len(record.fssai_no) != 14:
                    raise ValidationError(_("FSSAI number must consist of exactly 14 numeric digits."))

    def action_open_certificate_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Upload Certificate'),
            'res_model': 'partner.certificate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
            },
        }
