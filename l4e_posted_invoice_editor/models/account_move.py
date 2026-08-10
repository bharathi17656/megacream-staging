from odoo import models, fields, api, _

class AccountMove(models.Model):
    _inherit = 'account.move'

    is_posted_editable = fields.Boolean(
        string='Posted Editable',
        default=False,
        copy=False,
        help="Technical field to indicate if a posted invoice is currently in edit mode."
    )

    def action_posted_edit(self):
        for move in self:
            move.is_posted_editable = True

    def action_posted_done(self):
        for move in self:
            move.is_posted_editable = False

    def write(self, vals):
        if self.env.context.get('skip_readonly_check'):
            return super().write(vals)

        if any(move.state == 'posted' and move.is_posted_editable for move in self):
            return super(AccountMove, self.with_context(skip_readonly_check=True)).write(vals)

        return super().write(vals)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def write(self, vals):
        if any(line.move_id.state == 'posted' and line.move_id.is_posted_editable for line in self):
            return super(AccountMoveLine, self.with_context(skip_readonly_check=True)).write(vals)
        return super().write(vals)
