{
    'name': 'L4E Posted Invoice Editor',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Allows editing posted invoices with Edit and Done buttons',
    'description': """
        L4E Posted Invoice Editor
        =========================
        Module to enable editing posted invoices after confirmation.
        - Adds a blue 'Edit' button on posted invoices to make all fields editable.
        - Replaces the Edit button with a green 'Done' button when in editable mode.
    """,
    'author': 'L4E',
    'depends': ['account'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
