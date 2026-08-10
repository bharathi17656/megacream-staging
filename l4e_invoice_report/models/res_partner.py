from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    l4e_invoice_payment_term_id = fields.Many2one(
        comodel_name="account.payment.term",
        string="Invoice Payment Terms",
        help="Payment terms auto-applied to customer invoices for this contact.",
    )