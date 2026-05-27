# -*- coding: utf-8 -*-
{
    'name': 'Megacream Payroll PF & ESI Control',
    'version': '1.1',
    'summary': 'Toggle Provident Fund (PF) and ESI Deductions on Employees',
    'description': """
        Adds PF and ESI toggle booleans to Employee form view under Bank Salary Amount.
        If toggled off, PF/ESI are not deducted during Payslip Compute Sheet.
    """,
    'author': 'Vignesh',
    'category': 'Human Resources/Payroll',
    'depends': ['hr_payroll', 'adevx_hr_leave_rule'],
    'data': [
        'views/hr_employee_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
