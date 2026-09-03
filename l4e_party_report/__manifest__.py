# -*- coding: utf-8 -*-
{
    'name': 'MegaCream Party & Refrigerator Tracking',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Track Ice Cream Party Orders, Refrigerator Dispatches, Missing Fridges & Returns',
    'description': """
MegaCream Party & Refrigerator Tracking Module (Odoo 19)
=========================================================
Features:
- Track portable refrigerators/deep freezers dispatched with ice cream party orders.
- Monitor missing / pending refrigerator returns in real-time.
- Quick customer contact details (Phone, Email) for easy recovery follow-up.
- Wizard to quickly log refrigerator returns.
- Dedicated Party Report under Sales -> Reporting -> Party Report (below Customers).
- Pivot, Graph, and List views with filters for Missing, Overdue, and Completed returns.
    """,
    'author': 'L4E',
    'depends': ['sale', 'sale_management', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/fridge_return_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/party_report_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
