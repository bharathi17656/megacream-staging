{
    'name': 'Employee Increment',
    'version': '19.0.1.0.0',
    'author': 'Krishnaraj',
    'category': 'Human Resources',
    'summary': 'Manage employee salary increments and decrements with approval workflow',
    'depends': ['hr', 'hr_payroll', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/employee_increment_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
