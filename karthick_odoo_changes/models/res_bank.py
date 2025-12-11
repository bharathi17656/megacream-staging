from odoo import models, api, _ , fields
from odoo.exceptions import ValidationError

class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    iban_no = fields.Char(string="IBAN No")




# class AccountMove(models.Model):
#     _inherit = "account.move"

#     @api.constrains('invoice_line_ids', 'move_type')
#     def _check_invoice_against_po(self):
#         for move in self:
#             if move.move_type != 'in_invoice':
#                 continue

#             # Collect related POs from invoice lines
#             purchase_orders = move.invoice_line_ids.mapped('purchase_line_id.order_id')
#             for po in purchase_orders:
#                 # Get total PO amount
#                 po_total = po.amount_total

#                 # Get all posted bills linked to this PO
#                 posted_bills = self.env['account.move'].search([
#                     ('move_type', '=', 'in_invoice'),
#                     ('state', 'in', ['posted', 'draft']),
#                     ('invoice_line_ids.purchase_line_id.order_id', '=', po.id),
#                     ('id', '!=', move.id),
#                 ])

#                 billed_total = sum(posted_bills.mapped('amount_total')) + move.amount_total

#                 if billed_total > po_total + 0.0001:  # small tolerance
#                     raise ValidationError(_(
#                         "You cannot create this Bill because the total billed amount (%.2f) "
#                         "would exceed the Purchase Order total (%.2f) for PO %s."
#                     ) % (billed_total, po_total, po.name))




class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.constrains('quantity', 'price_unit')
    def _check_po_constraints(self):
        for line in self:
            if line.move_id.move_type == 'in_invoice' and line.purchase_line_id:
                po_line = line.purchase_line_id

                # 1. Validate Quantity (cannot exceed receivable qty)
                receivable_qty = po_line.qty_received - sum(
                    po_line.invoice_lines.filtered(lambda l: l.id != line.id).mapped('quantity')
                )
                if line.quantity > receivable_qty:
                    raise ValidationError(
                        f"⚠ You cannot bill more than the receivable quantity!\n"
                        f"PO Line: {po_line.product_id.display_name}\n"
                        f"Receivable Qty: {receivable_qty}, Entered: {line.quantity}"
                    )

                # 2. Validate Unit Price (cannot exceed PO unit price)
                if line.price_unit > po_line.price_unit:
                    raise ValidationError(
                        f"⚠ The unit price in the bill cannot exceed the PO unit price!\n"
                        f"PO Price: {po_line.price_unit}, Entered: {line.price_unit}"
                    )
