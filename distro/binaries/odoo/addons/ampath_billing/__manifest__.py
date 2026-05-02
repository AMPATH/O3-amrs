{
    'name': 'AMPATH Billing',
    'version': '1.0.38',
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
    'assets': {
        'web.assets_backend': [
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
