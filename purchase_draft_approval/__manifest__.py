# -*- coding: utf-8 -*-
{
    'name': 'Purchase Draft Approval',
    'version': '19.0.1.0.0',
    'category': 'Purchase',
    'summary': 'Adds Draft state to Purchase Orders with Procurement Manager approval before moving to RFQ',
    'description': """
        Purchase Draft Approval Module
        ================================
        - Adds a new 'Draft' state before RFQ in the Purchase workflow
        - When a Purchase Order is created, it starts in 'Draft' state
        - A 'Send to RFQ' button is available in Draft state
        - Clicking 'Send to RFQ' requires approval from Procurement Manager (Purchase Admin)
        - After approval, the order moves to RFQ state and continues the normal flow
        - Adds a 'Store Indent' boolean field on res.users
        - Users with 'Store Indent' enabled do NOT need to add a vendor in Draft state
    """,
    'author': 'Custom',
    'depends': ['purchase'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_activity_data.xml',
        'views/purchase_order_views.xml',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
