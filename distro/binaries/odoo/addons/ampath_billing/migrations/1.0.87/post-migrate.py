# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute(
        """
        ALTER TABLE stock_picking
            ADD COLUMN IF NOT EXISTS x_moh710_flow varchar;
        ALTER TABLE stock_location
            ADD COLUMN IF NOT EXISTS x_ampath_vaccine_store boolean;
        ALTER TABLE product_product
            ADD COLUMN IF NOT EXISTS x_ampath_vaccine boolean;
        ALTER TABLE product_category
            ADD COLUMN IF NOT EXISTS x_ampath_vaccine_category boolean;
        """
    )
    from odoo.addons.ampath_billing.hooks import (
        ensure_department_locations,
        ensure_vaccine_store_locations,
        tag_vaccine_products,
    )

    ensure_department_locations(env)
    ensure_vaccine_store_locations(env)
    tag_vaccine_products(env)
    _logger.info('ampath_billing 1.0.87: vaccine picking locations and product tags ensured')
