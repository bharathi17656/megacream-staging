from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Marks lines that were auto-created to carry a Transport / Transport Tax
    # charge onto the invoice. They still post real accounting amounts, but
    # are hidden from the "Invoice Lines" grid (see account_move_views.xml)
    # and shown instead as their own row in the totals breakdown widget.
    l4e_hide_charge_line = fields.Boolean(default=False, copy=False)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Overrides the domain of the existing invoice_line_ids field (core Odoo
    # already restricts it to display_type in product/line_section/line_note;
    # we add our own condition on top) so the hidden charge lines never show
    # up in the Invoice Lines grid, while still being real accounting lines.
    invoice_line_ids = fields.One2many(
        domain=[
            ('display_type', 'in', ('product', 'line_section', 'line_note')),
            ('l4e_hide_charge_line', '=', False),
        ],
    )

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            move._l4e_add_transport_charge_lines()
        return moves

    def _l4e_add_transport_charge_lines(self):
        self.ensure_one()
        if self.move_type != 'in_invoice' or not self.invoice_origin:
            return

        order = self.env['purchase.order'].search([('name', '=', self.invoice_origin)], limit=1)
        if not order:
            return

        transport = order.transport_charge_amount
        transport_tax = order.transport_charge_tax_amount
        if not transport and not transport_tax:
            return

        existing_names = self.invoice_line_ids.mapped('name')
        account = self.invoice_line_ids[:1].account_id or self.journal_id.default_account_id

        lines_vals = []
        if transport and 'Transport' not in existing_names:
            lines_vals.append((0, 0, {
                'name': 'Transport',
                'account_id': account.id if account else False,
                'quantity': 1,
                'price_unit': transport,
                'tax_ids': [(6, 0, [])],
                'l4e_hide_charge_line': True,
            }))
        if transport_tax and 'Transport Tax' not in existing_names:
            lines_vals.append((0, 0, {
                'name': 'Transport Tax',
                'account_id': account.id if account else False,
                'quantity': 1,
                'price_unit': transport_tax,
                'tax_ids': [(6, 0, [])],
                'l4e_hide_charge_line': True,
            }))
        if lines_vals:
            self.write({'invoice_line_ids': lines_vals})

    @api.depends(
        'invoice_line_ids.l4e_hide_charge_line',
        'invoice_line_ids.price_subtotal',
        'invoice_line_ids.name',
    )
    def _compute_tax_totals(self):
        super()._compute_tax_totals()
        for move in self:
            move._l4e_relabel_transport_charge_totals()

    def _l4e_relabel_transport_charge_totals(self):
        """Move the hidden Transport / Transport Tax line amounts out of the
        generic "Untaxed Amount" figure in the totals widget and show them as
        their own labeled rows instead - exactly like the sale/purchase order
        totals box. This only changes how the widget groups amounts for
        display; the real invoice lines (and the actual accounting/tax
        amounts) are completely untouched. Wrapped defensively so that if the
        totals widget's internal data shape ever changes, this simply becomes
        a no-op instead of breaking invoice computation.
        """
        self.ensure_one()
        charge_lines = self.invoice_line_ids.filtered(
            lambda l: l.l4e_hide_charge_line and l.name in ('Transport', 'Transport Tax')
        )
        if not charge_lines:
            return
        try:
            totals = self.tax_totals
            subtotals = totals and totals.get('subtotals')
            if not subtotals:
                return
            first = subtotals[0]
            tax_groups = list(first.get('tax_groups') or [])

            new_rows = []
            for label in ('Transport', 'Transport Tax'):
                amount = sum(charge_lines.filtered(lambda l: l.name == label).mapped('price_subtotal'))
                if not amount:
                    continue
                for base_key in ('base_amount_currency', 'base_amount',
                                  'display_base_amount_currency', 'display_base_amount'):
                    if base_key in first:
                        first[base_key] = first.get(base_key, 0.0) - amount
                new_rows.append({
                    'id': False, 'group_name': label, 'group_label': label,
                    'involved_tax_ids': [], 'base_amount_currency': 0.0, 'base_amount': 0.0,
                    'tax_amount_currency': amount, 'tax_amount': amount,
                    'display_base_amount_currency': 0.0, 'display_base_amount': 0.0,
                })

            if not new_rows:
                return

            first['tax_groups'] = new_rows + tax_groups
            subtotals[0] = first
            totals['subtotals'] = subtotals
            self.tax_totals = totals
        except Exception:
            return
