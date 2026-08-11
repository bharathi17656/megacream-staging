{
    'name': 'L4E Partner Custom Fields',
    'version': '19.0.1.0.0',
    'category': 'Contacts',
    'summary': 'Adds Vendor, Customer booleans and Certificates multi-attachment field to Contacts',
    'description': """
        L4E Partner Custom Fields
        =========================
        - Adds Vendor (is_vendor) and Customer (is_customer) boolean fields after Country.
        - Adds Certificates (certificate_ids) multi-attachment field below Tags with removal confirmation popup.
    """,
    'author': 'L4E',
    'depends': ['base', 'web'],
    'data': [
        'views/res_partner_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l4e_partner_custom_fields/static/src/fields/many2many_binary_confirm.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
