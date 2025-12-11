{
    'name': 'Karthick Odoo Changes',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Add SOR Details tab to Sale Order',
    'description': 'Adds start date, end date, and PO reference to Sale Orders under a new tab SOR Details.',
    'author': 'Karthick',
    'depends': ['web','sale','hr_attendance','hr_payroll'],
    'data': [
        'views/sale_order_views.xml',
    ],
     'assets': {
        'web.assets_backend': [
            # 'karthick_odoo_changes/static/src/attendance_row_progress_bar.xml', 
            # 'karthick_odoo_changes/static/src/attendance_row_progress_bar.js',
            # 'karthick_odoo_changes/static/src/custom_style.css'
        ],
    },
    'installable': True,
    'application': False,
}
