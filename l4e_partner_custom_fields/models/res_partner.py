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
    certificate_ids = fields.Many2many(
        'ir.attachment',
        'res_partner_certificate_rel',
        'partner_id',
        'attachment_id',
        string='Certificates',
        help="Upload certificate documents for this partner."
    )
    fssai_no = fields.Char(
        string='FSSAI',
        size=14,
        help="14-digit FSSAI License/Registration Number."
    )

    @api.constrains('fssai_no')
    def _check_fssai_no(self):
        for record in self:
            if record.fssai_no:
                if not record.fssai_no.isdigit() or len(record.fssai_no) != 14:
                    raise ValidationError(_("FSSAI number must consist of exactly 14 numeric digits."))

    def write(self, vals):
        partners_with_old_certs = {}
        if 'certificate_ids' in vals:
            for partner in self:
                partners_with_old_certs[partner.id] = set(partner.certificate_ids.ids)

        res = super().write(vals)

        if 'certificate_ids' in vals:
            for partner in self:
                old_ids = partners_with_old_certs.get(partner.id, set())
                new_ids = set(partner.certificate_ids.ids)
                removed_ids = old_ids - new_ids
                if removed_ids:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Certificate Removed'),
                            'message': _('Certificate file has been removed from this contact.'),
                            'type': 'warning',
                            'sticky': True,
                        }
                    }
        return res
