from odoo import models, fields,api
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _inherit = 'sale.order'


    main_head = fields.Boolean(string="Chairman")
    sub_head = fields.Boolean(string="Others")

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    poreference = fields.Char(string="PO Reference")


    # def action_confirm(self):
    #     for order in self:
    #         if not order.start_date or not order.end_date or not order.poreference:
    #             raise ValidationError("Start Date, End Date and PO Reference are required to confirm the Quotation.")
    #     return super(SaleOrder, self).action_confirm()

    custom_terms_conditions = fields.Html(
        string="Terms and Conditions",
        default=lambda self: self._default_terms()
    )

    @api.model
    def _default_terms(self):
        return """
        <p><strong>Terms and Conditions:</strong></p>
        <ol>
            <li>Normal Working Hours: 10 hours (compulsory).</li>
            <li>Normal Working days: 6 days in a week.</li>
            <li>Over Time: Normal Days: X 1.25 / Friday & Other holidays: X 1.5 = as per Qatar Labour Law.</li>
            <li>Medical, insurance and legal affairs: From Our side.</li>
            <li>Payment: Within 30 days from the date of invoice submission of every Month.</li>
            <li>Contract period: Minimum 3 months.</li>
            <li>Notice of Termination: At least before 7 days.</li>
            <li>Gate Pass Processing: By you.</li>
            <li>Time sheet: Should be handed over within the 5th of each month.</li>
            <li>Quotation Validity: Maximum 30 days.</li>
            <li>Food, Accommodation and Transportation: Provided by us.</li>
            <li>Safety: Normal Safety (Shoes, Helmets & Coveralls will be provided by us).</li>
            <li>If Extra Safety: Provided by you.</li>
        </ol>
        """



class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        for order in self:
            for line in order.order_line:
                if line.product_qty > 0:
                    # Update received qty equal to ordered qty
                    line.qty_received = line.product_qty
        return res




class AccountMove(models.Model):
    _inherit = "account.move"

    invoice_month_year = fields.Char(
        string="Invoice Month/Year",
        compute="_compute_invoice_month_year",
        store=True
    )

    
    main_head = fields.Boolean(string="Main Head")
    sub_head = fields.Boolean(string="Sub Head")
    

    @api.depends('invoice_date')
    def _compute_invoice_month_year(self):
        for record in self:
            if record.invoice_date:
                record.invoice_month_year = record.invoice_date.strftime('%B %Y').upper()
            else:
                record.invoice_month_year = False




# class ResCompany(models.Model):
#     _inherit = "res.company"

#     # Binary fields for signatures
#     head_signature = fields.Binary(string="Head Signature")
#     sub_head_signature = fields.Binary(string="Sub Head Signature")

#     # Users for head and sub-head
#     head_user_id = fields.Many2one('res.partner', string="Head User")
#     sub_head_user_id = fields.Many2one('res.partner', string="Sub Head User")

