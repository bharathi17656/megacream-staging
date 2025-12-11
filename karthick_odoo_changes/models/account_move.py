from datetime import datetime
from odoo import models, api
import re

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def create(self, vals):
        move = super().create(vals)
        if move.move_type in ('out_invoice', 'out_refund'):
            
            # Only assign if name is not already set
            if not move.name or move.name in ('/', 'WL0000/2025'):

                current_year = datetime.now().year

                # Find last WL number in existing invoices
                last_move = self.search([
                    ('name', 'like', 'WL%/%')
                ], order='id desc', limit=1)

                if last_move and last_move.name:
                    # Extract the numeric part using regex
                    match = re.search(r'WL(\d+)/\d+', last_move.name)
                    if match:
                        last_seq = int(match.group(1))
                    else:
                        last_seq = 0
                else:
                    last_seq = 0

                # Increment by 1
                new_seq = last_seq + 1

                move.name = f"WL{str(new_seq).zfill(4)}/{current_year}"

        return move
