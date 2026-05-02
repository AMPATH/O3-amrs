# -*- coding: utf-8 -*-
# Mekom odoo_initializer + AMPATH: add ``ampath_billing`` to ``depends`` so product fields
# (e.g. ``x_intervention_code``) exist before ``post_startup_hook`` CSV import.
{
    'name': "Odoo Initializer",

    'summary': """
        Odoo data Initializer""",

    'description': """
        Odoo add-on to import data provided as CSVs, loaded from a location on the server disk.
        This add-on helps implementers manage/deploy some of the Odoo data as files so to easily replicate environments.
        This add-on also specifically supports loading products and prices from an OpenMRS Initializer style CSV.
        See https://github.com/mekomsolutions/openmrs-module-initializer/
    """,

    'author': "Mekom Solutions",
    'website': "http://www.mekomsolutions.com",

    'category': 'Technical Settings',
    'version': '17.0.2.3.0',

    'depends': ['base', 'base_import', 'ampath_billing'],

    'application': True,
    'installable': True,
    'auto_install': True,
    'post_startup_hook': 'start_init',
}
