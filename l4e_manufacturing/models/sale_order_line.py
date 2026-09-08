# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    batch_id = fields.Many2one(
        "l4e.icecream.processing.batch",
        string="Batch Number",
        domain="['|', ('product_id', '=', product_id), ('output_line_ids.product_id', '=', product_id)]",
        help="Select the manufacturing processing batch issued to the customer.",
    )

    batch_ids = fields.Many2many(
        "l4e.icecream.processing.batch",
        "sale_order_line_batch_rel",
        "order_line_id",
        "batch_id",
        string="Batch Numbers",
        domain="['|', ('product_id', '=', product_id), ('output_line_ids.product_id', '=', product_id)]",
        help="Manufacturing processing batches allocated to this order line.",
    )

    batch_allocation_ids = fields.One2many(
        "l4e.sale.order.batch.allocation",
        "order_line_id",
        string="Batch Allocations",
    )

    lot_id = fields.Many2one(
        "stock.lot",
        string="Stock Lot",
    )

    batch_available_qty = fields.Float(
        string="Batch Avail. Qty",
        compute="_compute_batch_product_stock",
        readonly=True,
    )

    batch_status = fields.Selection(
        [
            ("in_stock", "In Stock"),
            ("finished", "Finished / Depleted"),
        ],
        string="Batch Status",
        compute="_compute_batch_product_stock",
        readonly=True,
    )

    @api.depends("batch_id", "product_id")
    def _compute_batch_product_stock(self):
        for line in self:
            if not line.batch_id or not line.product_id:
                line.batch_available_qty = 0.0
                line.batch_status = False
                continue
            batch_sudo = line.batch_id.sudo()
            output_lines = batch_sudo.output_line_ids.filtered(lambda ol: ol.product_id == line.product_id)
            if output_lines:
                prod_qty = sum(output_lines.mapped("net_quantity"))
            elif batch_sudo.product_id == line.product_id:
                prod_qty = batch_sudo.total_net_output_qty
            else:
                prod_qty = 0.0

            sold_lines = self.env["sale.order.line"].sudo().search([
                ("batch_id", "=", batch_sudo.id),
                ("product_id", "=", line.product_id.id),
                ("order_id.state", "in", ("sale", "done")),
                ("id", "!=", line.id if isinstance(line.id, int) else False),
            ])
            sold_qty = sum(sold_lines.mapped("product_uom_qty"))
            avail = prod_qty - sold_qty
            line.batch_available_qty = max(avail, 0.0)
            line.batch_status = "in_stock" if avail > 0 else "finished"

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        if self.batch_id:
            res["batch_id"] = self.batch_id.id
        if self.batch_ids:
            res["batch_ids"] = [(6, 0, self.batch_ids.ids)]
        return res

    def action_open_batch_split_wizard(self):
        self.ensure_one()
        if not self.product_id:
            raise UserError(_("Please select a product first before allocating batches."))
        return {
            "name": _("Allocate Batches: %s") % self.product_id.display_name,
            "type": "ir.actions.act_window",
            "res_model": "l4e.sale.order.batch.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_id": self.id,
                "active_model": "sale.order.line",
                "default_order_id": self.order_id.id,
                "default_order_line_id": self.id,
                "default_product_id": self.product_id.id,
                "default_required_qty": self.product_uom_qty or 1.0,
            },
        }

    @api.onchange("batch_ids")
    def _onchange_batch_ids(self):
        if self.batch_ids:
            if not self.batch_id or self.batch_id not in self.batch_ids:
                self.batch_id = self.batch_ids[0]
        else:
            self.batch_id = False

    @api.onchange("batch_id")
    def _onchange_batch_id_sync(self):
        if self.batch_id and self.batch_id not in self.batch_ids:
            self.batch_ids = [(4, self.batch_id.id)]

    @api.onchange("batch_id", "product_uom_qty")
    def _onchange_batch_quantity_check(self):
        if self.batch_id and self.product_uom_qty and self.batch_available_qty:
            if self.product_uom_qty > self.batch_available_qty and len(self.batch_ids) <= 1:
                return {
                    "warning": {
                        "title": _("Insufficient Batch Stock"),
                        "message": _(
                            "The selected batch '%(batch)s' only has %(avail).2f units available, but %(qty).2f was requested.\n\n"
                            "Tip: Click the 'Split Batch' button (cubes icon) on this line to allocate the quantity across multiple batches."
                        ) % {
                            "batch": self.batch_id.batch_number,
                            "avail": self.batch_available_qty,
                            "qty": self.product_uom_qty,
                        },
                    }
                }


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        for order in self:
            for line in order.order_line.filtered(lambda l: not l.display_type and l.product_id):
                # Check if product is managed with batches
                has_batches = self.env["l4e.icecream.processing.batch"].search_count([
                    "|",
                    ("product_id", "=", line.product_id.id),
                    ("output_line_ids.product_id", "=", line.product_id.id),
                ])
                if not has_batches:
                    continue

                # 1. Batch must be selected
                if not line.batch_ids and not line.batch_id:
                    raise ValidationError(
                        _("Cannot confirm %(order)s:\n\n"
                          "Please select or allocate a batch for product '%(product)s'.")
                        % {
                            "order": order.name,
                            "product": line.product_id.display_name,
                        }
                    )

                # 2. Check allocation completeness if multi-batch allocations exist
                if line.batch_allocation_ids:
                    total_alloc = sum(line.batch_allocation_ids.mapped("quantity"))
                    rounding = line.product_uom.rounding if line.product_uom else 0.01
                    if float_compare(total_alloc, line.product_uom_qty, precision_rounding=rounding) < 0:
                        rem = line.product_uom_qty - total_alloc
                        raise ValidationError(
                            _("Cannot confirm %(order)s:\n\n"
                              "Product '%(product)s' ordered quantity is %(qty).2f, but only %(alloc).2f units are allocated across batches (%(rem).2f remaining unallocated).\n\n"
                              "Please click 'Split Batch' on the line to allocate the remaining quantity, or adjust the ordered quantity to %(alloc).2f.")
                            % {
                                "order": order.name,
                                "product": line.product_id.display_name,
                                "qty": line.product_uom_qty,
                                "alloc": total_alloc,
                                "rem": rem,
                            }
                        )
                else:
                    # Single batch direct selection without multi-batch allocation records
                    if line.batch_id:
                        if line.product_uom_qty > line.batch_available_qty:
                            raise ValidationError(
                                _("Cannot confirm %(order)s:\n\n"
                                  "Batch '%(batch)s' for product '%(product)s' only has %(avail).2f units available, but %(qty).2f was requested.\n\n"
                                  "Please click 'Split Batch' on the line to allocate across multiple batches, or reduce the ordered quantity.")
                                % {
                                    "order": order.name,
                                    "batch": line.batch_id.batch_number,
                                    "product": line.product_id.display_name,
                                    "avail": line.batch_available_qty,
                                    "qty": line.product_uom_qty,
                                }
                            )

        return super().action_confirm()
