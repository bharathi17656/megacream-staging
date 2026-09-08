# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class L4eSaleOrderBatchWizard(models.TransientModel):
    _name = 'l4e.sale.order.batch.wizard'
    _description = 'Sale Order Multi-Batch Allocation Wizard'

    order_id = fields.Many2one('sale.order', string='Sale Order', required=True, readonly=True)
    order_line_id = fields.Many2one('sale.order.line', string='Order Line', required=True, readonly=True)
    product_id = fields.Many2one('product.product', string='Product', required=True, readonly=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id', readonly=True)
    required_qty = fields.Float(
        string='Required Quantity',
        required=True,
        digits='Product Unit of Measure',
    )
    allocated_qty = fields.Float(
        string='Total Allocated',
        compute='_compute_allocation_totals',
        digits='Product Unit of Measure',
    )
    remaining_qty = fields.Float(
        string='Remaining to Allocate',
        compute='_compute_allocation_totals',
        digits='Product Unit of Measure',
    )
    allocation_line_ids = fields.One2many(
        'l4e.sale.order.batch.wizard.line',
        'wizard_id',
        string='Batch Allocations',
    )

    @api.depends('allocation_line_ids.allocated_qty', 'required_qty')
    def _compute_allocation_totals(self):
        for wiz in self:
            alloc = sum(wiz.allocation_line_ids.mapped('allocated_qty'))
            wiz.allocated_qty = alloc
            wiz.remaining_qty = max(0.0, wiz.required_qty - alloc)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line_id = self.env.context.get('active_id')
        if not line_id or self.env.context.get('active_model') != 'sale.order.line':
            return res

        line = self.env['sale.order.line'].browse(line_id)
        if not line.exists() or not line.product_id:
            return res

        res.update({
            'order_id': line.order_id.id,
            'order_line_id': line.id,
            'product_id': line.product_id.id,
            'required_qty': line.product_uom_qty or 1.0,
        })

        existing_allocations = {
            alloc.batch_id.id: alloc.quantity
            for alloc in line.batch_allocation_ids
        }

        in_stock_batch_ids = self.env['l4e.icecream.processing.batch']._get_in_stock_batch_ids_by_product(line.product_id.id)
        batch_ids_to_fetch = set(in_stock_batch_ids) | set(existing_allocations.keys())
        batches = self.env['l4e.icecream.processing.batch'].browse(list(batch_ids_to_fetch)).sorted(key=lambda b: (b.date or fields.Date.today(), b.id))

        lines_commands = []
        for batch in batches:
            matching_output = batch.output_line_ids.filtered(lambda ol: ol.product_id == line.product_id)
            if matching_output:
                prod_qty = sum(matching_output.mapped('net_quantity'))
            elif batch.product_id == line.product_id:
                prod_qty = batch.total_net_output_qty
            else:
                prod_qty = 0.0

            sold_allocs = self.env['l4e.sale.order.batch.allocation'].sudo().search([
                ('batch_id', '=', batch.id),
                ('order_id.state', 'in', ('sale', 'done')),
                ('order_line_id', '!=', line.id),
            ])
            sold_from_allocs = sum(sold_allocs.mapped('quantity'))

            sold_legacy_lines = self.env['sale.order.line'].sudo().search([
                ('batch_id', '=', batch.id),
                ('product_id', '=', line.product_id.id),
                ('order_id.state', 'in', ('sale', 'done')),
                ('id', '!=', line.id),
                ('batch_allocation_ids', '=', False),
            ])
            sold_from_legacy = sum(sold_legacy_lines.mapped('product_uom_qty'))
            sold_qty = sold_from_allocs + sold_from_legacy

            avail = max(0.0, prod_qty - sold_qty)
            current_allocated = min(existing_allocations.get(batch.id, 0.0), avail)

            if avail > 0 or current_allocated > 0:
                lines_commands.append((0, 0, {
                    'batch_id': batch.id,
                    'available_qty': avail,
                    'allocated_qty': current_allocated,
                }))

        res['allocation_line_ids'] = lines_commands
        return res

    def action_auto_allocate_fifo(self):
        self.ensure_one()
        remaining = self.required_qty
        for line in self.allocation_line_ids.sorted(key=lambda l: (l.date or fields.Date.today(), l.id)):
            if remaining <= 0:
                line.allocated_qty = 0.0
            else:
                take = min(line.available_qty, remaining)
                line.allocated_qty = take
                remaining -= take

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_apply(self):
        self.ensure_one()
        alloc_lines = self.allocation_line_ids.filtered(lambda l: l.allocated_qty > 0)
        if not alloc_lines:
            raise UserError(_('Please allocate at least one batch with quantity greater than 0.'))

        if self.allocated_qty > self.required_qty:
            raise ValidationError(
                _('Total allocated quantity (%(alloc).2f) cannot exceed the required quantity (%(req).2f).')
                % {'alloc': self.allocated_qty, 'req': self.required_qty}
            )

        sorted_alloc = alloc_lines.sorted(key=lambda l: (l.date or fields.Date.today(), l.id))
        batch_ids_list = [alloc.batch_id.id for alloc in sorted_alloc]
        alloc_commands = [(5, 0, 0)]
        for alloc in sorted_alloc:
            alloc_commands.append((0, 0, {
                'batch_id': alloc.batch_id.id,
                'quantity': alloc.allocated_qty,
            }))

        self.order_line_id.write({
            'batch_ids': [(6, 0, batch_ids_list)],
            'batch_id': batch_ids_list[0] if batch_ids_list else False,
            'batch_allocation_ids': alloc_commands,
        })

        return {'type': 'ir.actions.act_window_close'}


class L4eSaleOrderBatchWizardLine(models.TransientModel):
    _name = 'l4e.sale.order.batch.wizard.line'
    _description = 'Sale Order Batch Allocation Wizard Line'
    _order = 'date asc, id asc'

    wizard_id = fields.Many2one('l4e.sale.order.batch.wizard', string='Wizard', ondelete='cascade', required=True)
    batch_id = fields.Many2one('l4e.icecream.processing.batch', string='Batch', required=True)
    batch_number = fields.Char(string='Batch Number', related='batch_id.batch_number', readonly=True)
    date = fields.Date(string='Batch Date', related='batch_id.date', readonly=True)
    available_qty = fields.Float(string='Available Stock', digits='Product Unit of Measure')
    allocated_qty = fields.Float(string='Quantity to Take', digits='Product Unit of Measure', default=0.0)

    @api.constrains('allocated_qty', 'available_qty')
    def _check_allocated_qty(self):
        for line in self:
            if line.allocated_qty < 0:
                raise ValidationError(_('Allocated quantity cannot be negative for batch %s.') % line.batch_number)
            if line.allocated_qty > line.available_qty:
                raise ValidationError(
                    _('Cannot allocate %(qty).2f from batch %(batch)s because only %(avail).2f is available.')
                    % {'qty': line.allocated_qty, 'batch': line.batch_number, 'avail': line.available_qty}
                )
