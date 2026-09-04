# -*- coding: utf-8 -*-
{
    'name': 'MegaCream Processing & Batch Management',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Manufacturing',
    'summary': 'Ice Cream Manufacturing, Batch Tracking & Sales Dispatch Reporting',
    'description': """
MegaCream Ice Cream Manufacturing & Batch Management Module (Odoo 19)
=======================================================================
Features:
- Processing Batches: Manage raw material conversion into finished ice cream products
- Batch Sequencing: Daily resetting batch numbers (BATCH-DD-MMM-YY-001)
- Batch Selection: Dropdown on Sales Orders and Invoices with live availability status
- Inactivity / Finished Batch Indicators: Real-time stock status (In Stock vs Finished/Depleted)
- Inventory Batch Dispatch & Sales Report: Traceability of whom batches were given/sold to, quantities, and values
- Processing Cost Report: Financial variance and yield tracking
    """,
    'author': 'L4E',
    'depends': ['stock', 'mail', 'sale', 'sale_management', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/l4e_data.xml',
        'views/l4e_processing_batch_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'views/batch_dispatch_report_views.xml',
        'views/actions.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
