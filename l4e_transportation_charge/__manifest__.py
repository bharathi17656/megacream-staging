{
    'name': 'L4E Transportation Charge',
    'version': '19.0.1.0.0',
    'summary': 'Transportation Charge wizard for Sale and Purchase orders',
    'category': 'Sales',
    'author': 'L4E',
    'depends': ['sale', 'purchase', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/transportation_charge_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
}