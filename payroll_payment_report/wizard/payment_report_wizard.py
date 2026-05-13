from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class PaymentReportWizard(models.TransientModel):
    _name = 'payment.report.wizard'
    _description = 'Payment Report Wizard'

    date_from = fields.Date(
        string='From Date',
        required=True,
        default=fields.Date.context_today
    )
    date_to = fields.Date(
        string='To Date',
        required=True,
        default=fields.Date.context_today
    )
    payment_type = fields.Selection([
        ('bank', 'Bank Transfer'),
        ('cash', 'Cash Payment'),
        ('all', 'All'),
    ], string='Payment Filter', required=True, default='all')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from > rec.date_to:
                raise ValidationError(_("From Date cannot be greater than To Date."))

    def action_generate_report(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/payment/report/xlsx?wizard_id=%d' % self.id,
            'target': 'new',
        }