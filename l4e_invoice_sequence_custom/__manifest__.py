{
    'name': 'L4E Custom Invoice, Bill, SO, PO & DO Sequence',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Custom sequence format (AUG/INV/001/26-27) for Invoices, Bills, Sale Orders, Purchase Orders, and Delivery Orders',
    'description': """
        L4E Custom Sequence Module
        ==========================
        Overrides naming convention for:
        - Customer Invoices: AUG/INV/001/26-27
        - Vendor Bills: AUG/BIL/001/26-27
        - Sale Orders: AUG/SO/001/26-27
        - Purchase Orders: AUG/PO/001/26-27
        - Delivery Orders: AUG/DO/001/26-27

        - Resets sequence to 001 at the beginning of each month.
        - Includes manual scheduled actions (crons) to update old records.
    """,
    'author': 'L4E',
    'depends': ['account', 'sale_management', 'purchase', 'stock'],
    'data': [
        'data/ir_cron_data.xml',
        'views/stock_picking_views.xml',   
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
