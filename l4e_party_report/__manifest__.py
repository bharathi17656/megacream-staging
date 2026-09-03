# -*- coding: utf-8 -*-
{
    'name': 'MegaCream Party & Customer Inactivity Report',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Track Inactive Customers & Last Sale Order Activity for Customer Retention',
    'description': """
MegaCream Party & Customer Inactivity Report Module (Odoo 19)
==============================================================
Features:
- Track customer inactivity based on days elapsed since their last Sales Order.
- Quick customer contact details (Phone, Email, City/State) for follow-up calls.
- Time-based filters: Inactive > 1 Month (30 Days), > 2 Months (60 Days), > 3 Months (90 Days), Dormant, Active.
- Dedicated Party Report under Sales -> Reporting -> Party Report (below Customers).
- Pivot, Graph, and List views with tier grouping and lifetime revenue metrics.
    """,
    'author': 'L4E',
    'depends': ['sale', 'sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/party_report_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
