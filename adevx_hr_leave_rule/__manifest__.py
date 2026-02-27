{
    "name": "HR Leave Rule",
    "summary": "HR Leave Rule",
    "description": "HR Leave Rule",

    'author': 'Links4Engg',
    'category': 'Generic Modules/Human Resources',
    "license": "OPL-1",
    "depends": ["hr", 'hr_holidays','hr_payroll'],
    "data": [
        # Security
        "security/leave_access_group.xml",
        'security/ir.model.access.csv',

        # Views
        'views/hr_group_leave_views.xml',
        # 'views/hr_attendance_approval_views.xml',
        # "views/hr_leave_rule.xml",
        # "views/hr_leave_type.xml",
        # "views/hr_leave_allocation.xml",
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
