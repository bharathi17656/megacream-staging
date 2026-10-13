{
    'name': 'L4E Delivery Address',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Separate Delivery Address for Quotations, Invoices, and Reports',
    'description': """
        L4E Delivery Address
        ====================
        - Adds a dedicated 'Delivery Address' tab on Quotations/Sales Orders after Other Info.
        - Adds a corresponding 'Delivery Address' tab on Customer Invoices.
        - Automatically transfers delivery address from Quotations to Invoices upon invoice creation.
        - Adds 'Copy Customer Address' and 'Clear' quick actions.
        - Updates Quotation and Tax Invoice reports with side-by-side 'Billing Address' (left)
          and 'Delivery Address' (right) boxes, hiding Delivery Address when not provided.
    """,
    'author': 'L4E',
    'depends': [
        'sale',
        'account',
    ],
    'data': [
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'reports/sale_order_report_templates.xml',
        'reports/invoice_report_templates.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
