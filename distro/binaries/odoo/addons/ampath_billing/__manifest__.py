{
    'name': 'AMPATH Billing',
    'version': '1.0.7',
    'summary': 'Billing module for AMPATH',
    'category': 'Healthcare/Accounting',
    'author': 'AMPATH',
    'depends': ['sale', 'account', 'odoo_initializer'],
    'data': [
        'security/ir.model.access.csv',
        'data/landing_page.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
    'assets': {},
    'installable': True,
    'application': True,
    'auto_install': True,
    'license': 'LGPL-3',
}
