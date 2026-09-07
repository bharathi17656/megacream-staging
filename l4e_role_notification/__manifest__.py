# -*- coding: utf-8 -*-
{
    'name': 'L4E Role Notification',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Notify Store/Production users when a Sales User confirms a Sale Order',
    'description': """
L4E Role Notification
======================
- Adds three role checkboxes on the User form (Access Rights tab): Store User, Production User, Sales User.
- When a user flagged as Sales User confirms a Sale Order (Quotation -> Sales Order),
  all users flagged as Store User or Production User receive an inbox notification
  (and a chatter log on the order) with the order details.
    """,
    'author': 'L4E',
    'depends': ['base', 'sale'],
    'data': [
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
