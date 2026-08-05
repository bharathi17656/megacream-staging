from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l4e_item_code = fields.Char(
        string="Item Code"
    )