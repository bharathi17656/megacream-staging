{
    'name': 'L4E Purchase Order Report Custom',
    'version': '19.0.1.0.0',
    'category': 'Purchase',
    'summary': 'Displays Contact No, Email, GST Treatment, GSTIN and FSSAI under address in Purchase Order report',
    'description': """
        L4E Purchase Order Report Custom
        ================================
        Customizes Purchase Order & RFQ PDF reports to display:
        - Vendor Email
        - Vendor Phone / Mobile
        - GST Treatment
        - GSTIN
        - FSSAI Number
        under the vendor address block.
    """,
    'author': 'L4E',
    'depends': ['purchase', 'l4e_partner_custom_fields'],
    'data': [
        'views/purchase_order_report_templates.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
