# -*- coding: utf-8 -*-
{
    'name': 'L4E Customer Pricelist',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Per-customer product pricing that overrides Sale Order line price without touching product Sales Price',
    'description': """
L4E Customer Pricelist
=======================
- Adds a "Products" tab on the Contact form (visible only when "Customer" is checked)
- Maintain a per-customer price list: Product, Actual Price (from Sales Price, read-only), Customer Price (manual)
- On Sale Order lines, if the ordering customer has a Customer Price for the product, it is used
  as the line's price_unit. The product's own Sales Price in Inventory/Sales is never modified.
    """,
    'author': 'L4E',
    'depends': ['base', 'contacts', 'sale', 'l4e_partner_custom_fields'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/l4e_customer_group_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
