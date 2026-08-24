from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Marks lines that were auto-created to carry the Packing charge onto the
    # invoice. They still post real accounting amounts, but are hidden from
    # the "Invoice Lines" grid (see account_move_views.xml) and shown instead
    # as their own row in the totals breakdown widget.
    l4e_hide_charge_line = fields.Boolean(default=False, copy=False)


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.depends(
        'invoice_line_ids.l4e_hide_charge_line',
        'invoice_line_ids.price_subtotal',
        'invoice_line_ids.name',
    )
    def _compute_tax_totals(self):
        super()._compute_tax_totals()
        for move in self:
            move._l4e_relabel_packing_charge_totals()

    def _l4e_relabel_packing_charge_totals(self):
        """Move the hidden Packing charge line amount out of the generic
        "Untaxed Amount" figure in the totals widget and show it as its own
        labeled row instead - exactly like the sale order totals box. This
        only changes how the widget groups amounts for display; the real
        invoice line (and the actual accounting amount) is completely
        untouched. Wrapped defensively so that if the totals widget's
        internal data shape ever changes, this simply becomes a no-op
        instead of breaking invoice computation.
        """
        self.ensure_one()
        charge_lines = self.invoice_line_ids.filtered(
            lambda l: l.l4e_hide_charge_line and l.name and l.name.startswith('Packing charge')
        )
        if not charge_lines:
            return
        try:
            amount = sum(charge_lines.mapped('price_subtotal'))
            if not amount:
                return

            totals = self.tax_totals
            subtotals = totals and totals.get('subtotals')
            if not subtotals:
                return
            first = subtotals[0]
            tax_groups = list(first.get('tax_groups') or [])

            for base_key in ('base_amount_currency', 'base_amount',
                              'display_base_amount_currency', 'display_base_amount'):
                if base_key in first:
                    first[base_key] = first.get(base_key, 0.0) - amount

            tax_groups.insert(0, {
                'id': False, 'group_name': 'Packing charge', 'group_label': 'Packing charge',
                'involved_tax_ids': [], 'base_amount_currency': 0.0, 'base_amount': 0.0,
                'tax_amount_currency': amount, 'tax_amount': amount,
                'display_base_amount_currency': 0.0, 'display_base_amount': 0.0,
            })

            first['tax_groups'] = tax_groups
            subtotals[0] = first
            totals['subtotals'] = subtotals
            self.tax_totals = totals
        except Exception:
            return
