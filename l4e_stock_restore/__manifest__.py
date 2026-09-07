# -*- coding: utf-8 -*-
{
    'name': 'L4E Stock Restore',
    'version': '19.0.1.0.0',
    'category': 'Manufacturing/Inventory',
    'summary': 'Stock Restore menu in Manufacturing for Production Users to create Draft Internal Transfers with Store User notifications',
    'description': """
L4E Stock Restore
=================
- Adds 'Stock restore' master menu in Manufacturing module.
- Allows Production Users to create Internal Transfers in Draft stage.
- Production Users are restricted to Draft stage (cannot mark as todo or validate).
- Automatically notifies Store Users in Odoo Discuss (Inbox & Chat) and Chatter with transfer and product details.
- Store Users can then process the transfer in Inventory -> Internal Transfers.
    """,
    'author': 'L4E',
    'depends': ['base', 'mail', 'stock', 'mrp', 'l4e_role_notification'],
    'data': [
        'views/stock_picking_views.xml',
        'views/mrp_menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
