from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    accounts_contact_number = fields.Char(
        string="Accounts Contact Number"
    )

    sales_contact_number = fields.Char(
        string="Sales Contact Number"
    )