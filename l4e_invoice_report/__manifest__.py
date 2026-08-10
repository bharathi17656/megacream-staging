{
    "name": "L4E Invoice Report Customization",
    "version": "19.0.1.0.0",
    "summary": "Adds missing seller/customer/bank/HSN details to the invoice PDF",
    "category": "Accounting/Accounting",
    "author": "Links4Engg",
    "license": "OPL-1",
    "depends": [
        "account",
        "sale",
        "l10n_in",
        "l4e_custom_fields",
    ],
    "data": [
        "views/product_template_views.xml",
        "views/res_partner_views.xml",
        "views/account_move_views.xml",
        "report/invoice_report_template.xml",
        "report/external_layout_l4e.xml",
    ],
    "installable": True,
    "application": False,
}