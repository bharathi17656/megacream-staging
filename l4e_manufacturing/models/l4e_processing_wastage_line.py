# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class L4eIceCreamWastageReason(models.Model):
    _name = "l4e.icecream.wastage.reason"
    _description = "Ice Cream Wastage Reason"
    _order = "sequence, name"

    name = fields.Char(string="Reason Name", required=True, translate=True)
    code = fields.Char(string="Code")
    description = fields.Text(string="Description")
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)


class L4eIceCreamWastageLine(models.Model):
    _name = "l4e.icecream.wastage.line"
    _description = "Ice Cream Processing Wastage Line"
    _order = "date desc, id desc"

    batch_id = fields.Many2one(
        "l4e.icecream.processing.batch",
        string="Processing Batch",
        required=True,
        ondelete="cascade",
        index=True,
    )

    batch_name = fields.Char(
        string="Batch Number",
        related="batch_id.name",
        store=True,
        index=True,
    )

    date = fields.Date(
        string="Date",
        related="batch_id.date",
        store=True,
        index=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        domain="[('type', 'in', ['product', 'consu'])]",
    )

    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot / Batch No",
        domain="[('product_id', '=', product_id)]",
    )

    packaging_no = fields.Char(
        string="Packaging / Tub No",
        help="Tub number, crate number, or packaging reference",
    )

    quantity = fields.Float(
        string="Wastage Quantity",
        required=True,
        default=1.0,
        digits="Product Unit of Measure",
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="UoM",
        related="product_id.uom_id",
        readonly=True,
        store=True,
    )

    reason_id = fields.Many2one(
        "l4e.icecream.wastage.reason",
        string="Reason",
        required=True,
        ondelete="restrict",
    )

    unit_cost = fields.Float(
        string="Unit Cost",
        compute="_compute_unit_cost",
        store=True,
        readonly=False,
        digits="Product Price",
    )

    total_loss_value = fields.Float(
        string="Total Loss Value",
        compute="_compute_total_loss_value",
        store=True,
        digits="Product Price",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="batch_id.company_id",
        store=True,
        index=True,
    )

    remarks = fields.Char(string="Remarks")

    allowed_product_ids = fields.Many2many(
        "product.product",
        compute="_compute_allowed_product_ids",
        string="Allowed Products",
    )

    @api.depends("batch_id.output_line_ids.product_id")
    def _compute_allowed_product_ids(self):
        for line in self:
            if line.batch_id and line.batch_id.output_line_ids:
                line.allowed_product_ids = line.batch_id.output_line_ids.mapped("product_id")
            else:
                line.allowed_product_ids = self.env["product.product"]

    @api.constrains("product_id", "batch_id")
    def _check_product_in_finished_products(self):
        for line in self:
            if line.batch_id and line.product_id:
                finished_prods = line.batch_id.output_line_ids.mapped("product_id")
                if finished_prods and line.product_id not in finished_prods:
                    raise ValidationError(
                        _("The product '%(product)s' in Wastage must be one of the finished products in the Finished Product tab.")
                        % {"product": line.product_id.display_name}
                    )

    @api.depends("product_id", "product_id.standard_price", "product_id.list_price", "batch_id.output_line_ids.unit_price", "batch_id.output_line_ids.product_id")
    def _compute_unit_cost(self):
        for line in self:
            price = 0.0
            if line.batch_id and line.product_id:
                matching_output = line.batch_id.output_line_ids.filtered(lambda o: o.product_id == line.product_id)
                if matching_output and matching_output[0].unit_price:
                    price = matching_output[0].unit_price
            if not price and line.product_id:
                price = line.product_id.list_price or line.product_id.standard_price or 0.0
            line.unit_cost = price

    @api.depends("quantity", "unit_cost")
    def _compute_total_loss_value(self):
        for line in self:
            line.total_loss_value = (line.quantity or 0.0) * (line.unit_cost or 0.0)
