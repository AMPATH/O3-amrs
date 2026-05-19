{
    'name': 'AMPATH Billing',
    'version': '1.0.59',
    'summary': 'Billing module for AMPATH',
    'category': 'Healthcare/Accounting',
    'author': 'AMPATH',
    'depends': ['web', 'sale', 'sale_stock', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/landing_page.xml',
        'views/ampath_payload_preview_wizard_views.xml',
        'views/ampath_claim_submit_result_wizard_views.xml',
        'report/sale_order_prescription_report.xml',
        'wizards/views/prescription_print_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'views/product_template_views.xml',
    ],
    # Login / public pages use web.assets_frontend, which pulls primary_variables via
    # web._assets_helpers → web._assets_primary_variables — not web.assets_backend.
    # Patch the shared bundle so backend, login, and other consumers all see AMPATH colours.
    'assets': {
        'web._assets_primary_variables': [
            (
                'before',
                'web/static/src/scss/primary_variables.scss',
                'ampath_billing/static/src/scss/ampath_brand_variables.scss',
            ),
            # After core primary_variables so Mekom/other *.variables.scss cannot
            # leave community purple as the effective brand for derived maps.
            (
                'after',
                'web/static/src/scss/primary_variables.scss',
                'ampath_billing/static/src/scss/ampath_brand_override_primary.scss',
            ),
        ],
        # Explicit rules for public login (/web/login); survives variable merge issues.
        'web.assets_frontend': [
            'ampath_billing/static/src/scss/ampath_brand_login.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': True,
    'license': 'LGPL-3',
}
