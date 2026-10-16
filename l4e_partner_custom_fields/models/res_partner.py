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

    @api.constrains(
        'vat',
        'accounts_contact_number',
        'accounts_name',
        'salesperson_name',
        'sales_contact_number',
        'store_person_name',
        'store_person_number',
        'parent_id',
    )
    def _check_mandatory_contact_fields(self):
        if self.env.context.get('install_mode') or self.env.context.get('skip_partner_mandatory_fields'):
            return
        root_partner = self.env.ref('base.partner_root', raise_if_not_found=False)
        root_partner_id = root_partner.id if root_partner else False
        for record in self:
            if root_partner_id and record.id == root_partner_id:
                continue
            if record.user_ids:
                continue
            if not record.parent_id:
                missing = []
                if not record.vat or not str(record.vat).strip():
                    missing.append(_("GSTIN"))
                if not record.accounts_contact_number or not str(record.accounts_contact_number).strip():
                    missing.append(_("Accounts Contact Number"))
                if not record.accounts_name or not str(record.accounts_name).strip():
                    missing.append(_("Accounts Name"))
                if not record.salesperson_name or not str(record.salesperson_name).strip():
                    missing.append(_("Salesperson Name"))
                if not record.sales_contact_number or not str(record.sales_contact_number).strip():
                    missing.append(_("Sales Contact Number"))
                if not record.store_person_name or not str(record.store_person_name).strip():
                    missing.append(_("Store Person Name"))
                if not record.store_person_number or not str(record.store_person_number).strip():
                    missing.append(_("Store Person Number"))

                if missing:
                    missing_str = "\n".join(f"• {field_name}" for field_name in missing)
                    raise ValidationError(
                        _("The following fields are mandatory to save contact '%s':\n%s")
                        % (record.display_name or record.name or '', missing_str)
                    )

    @api.constrains('is_vendor', 'certificate_ids')
    def _check_vendor_certificate(self):
        if self.env.context.get('install_mode') or self.env.context.get('skip_vendor_cert_check'):
            return
        for record in self:
            if record.is_vendor and not record.certificate_ids:
                raise ValidationError(
                    _("Please upload at least one certificate in the 'Certificates' tab before saving Vendor '%s'.")
                    % (record.display_name or record.name or '')
                )

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


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        return super(ResUsers, self.with_context(skip_partner_mandatory_fields=True)).create(vals_list)

