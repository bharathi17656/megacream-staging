{
    'name': 'L4E Custom Invoice & Bill Sequence',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Custom sequence format (AUG/INV/001/26-27) for Invoices and Bills',
    'description': """
        L4E Custom Invoice & Bill Sequence
        ==================================
        Overrides Customer Invoice and Vendor Bill naming convention:
        - Format: MMM/TYPE/SEQ/FY (e.g. AUG/INV/001/26-27 or AUG/BIL/001/26-27)
        - Resets to 001 at the beginning of each month.
        - Includes 2 manual scheduled actions (crons) to update old records.
    """,
    'author': 'L4E',
    'depends': ['account'],
    'data': [
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
