{
    'name': 'L4E Partner Custom Fields',
    'version': '19.0.1.0.0',
    'category': 'Contacts',
    'summary': 'Adds Vendor, Customer booleans and Certificates with expiration date to Contacts',
    'description': """
        L4E Partner Custom Fields
        =========================
        - Adds Vendor (is_vendor) and Customer (is_customer) boolean fields after Country.
        - Adds FSSAI number field.
        - Adds Certificates (certificate_ids) with name, file, and expiration date via upload wizard.
    """,
    'author': 'L4E',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/partner_certificate_wizard_views.xml',
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
