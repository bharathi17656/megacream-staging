from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    amount_paid = fields.Monetary(
        string='Paid Amount',
        compute='_compute_amount_paid',
        currency_field='currency_id',
    )

    @api.depends('amount_total', 'amount_residual')
    def _compute_amount_paid(self):
        for move in self:
            move.amount_paid = move.amount_total - move.amount_residual