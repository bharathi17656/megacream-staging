# -*- coding: utf-8 -*-
{
    'name': 'Employee Salary Report',
    'version': '19.0.1',
    'summary': 'Generate salary reports automatically from payslips',
    'description': """
Creates employee.salary.report records when payslips are validated.
Includes:
- Basic
- HRA
- Allowances
- PF / ESI
- Deductions
- Net Salary
- CTC
""",
    'author': 'L4E',
    'category': 'Human Resources/Payroll',
    'depends': [
        'hr',
        'hr_payroll',
        'hr_attendance',
        'hr_holidays'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/employee_salary_report_views.xml',
    ],
    'installable': True,
    'application': False,
}
