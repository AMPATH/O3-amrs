{
    'name': 'AMPATH Billing',
    'version': '1.0.51',
    'summary': 'Billing module for AMPATH',
    'category': 'Healthcare/Accounting',
    'author': 'AMPATH',
    'depends': ['web', 'sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/landing_page.xml',
        'views/ampath_payload_preview_wizard_views.xml',
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
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': True,
    'license': 'LGPL-3',
}
