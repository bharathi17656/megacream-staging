# -*- coding: utf-8 -*-
{
    'name': 'L4E Role Notification',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Notify Store and Production users in Discuss and Chatter when a Sales User creates/confirms a Sale Order',
    'description': """
L4E Role Notification
======================
- Adds three role checkboxes on the User form: Store User, Production User, Sales User.
- When a user flagged as Sales User creates or confirms a Sale Order,
  all users flagged as Store User or Production User receive notifications
  in Odoo Discuss (Inbox and Direct Chat) as well as the order chatter with order details and items.
    """,
    'author': 'L4E',
    'depends': ['base', 'mail', 'sale'],
    'data': [
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
