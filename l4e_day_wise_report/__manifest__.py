{
    'name': 'L4E Day Wise Report',
    'version': '19.0.1.0.0',
    'summary': 'Day-wise report menu for Sale Orders and Invoices',
    'category': 'Sales',
    'author': 'L4E',
    'depends': ['sale', 'account', 'purchase'],
    'data': [
        'views/sale_order_report_views.xml',
        'views/account_move_report_views.xml',
        'views/purchase_bill_report_views.xml',
        'views/purchase_outstanding_report_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
}
