{
    'name': 'Payroll Payment Report',
    'version': '19.0.1.1',
    'summary': 'Custom Payment Report for Cash and Bank Transfer',
    'category': 'Human Resources/Payroll',
    'depends': [
        'hr_payroll',
        'adevx_hr_leave_rule',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/payment_report_wizard_view.xml',
        'views/payment_report_menu.xml',
        'report/payment_report_template.xml',
    ],
    'installable': True,
    'application': False,
    'author': 'Company',
    'license': 'LGPL-3',
}
