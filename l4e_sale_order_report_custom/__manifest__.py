{
    'name': 'L4E Sale Order Report Custom',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Displays Contact No, Email, GST Treatment, GSTIN and FSSAI under address in Sale Order report',
    'description': """
        L4E Sale Order Report Custom
        ============================
        Customizes the Sale Order PDF report to display:
        - Customer Email
        - Customer Phone / Mobile
        - GST Treatment
        - GSTIN
        - FSSAI Number
        under the customer address block.
    """,
    'author': 'L4E',
    'depends': ['sale', 'l4e_partner_custom_fields'],
    'data': [
        'views/sale_order_report_templates.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
