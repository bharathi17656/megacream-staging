{
    'name': 'L4E Dry Ice Packing Charge',
    'version': '19.0.1.0.0',
    'summary': 'Dry Ice Packing Charge wizard for Sale orders',
    'category': 'Sales',
    'author': 'L4E',
    'depends': ['sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/dry_ice_packing_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
}
