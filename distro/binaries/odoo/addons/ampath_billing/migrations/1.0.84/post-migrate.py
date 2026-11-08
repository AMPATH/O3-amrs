# -*- coding: utf-8 -*-

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        ALTER TABLE stock_location
            ADD COLUMN IF NOT EXISTS x_ampath_external_transit boolean;
        ALTER TABLE stock_picking
            ADD COLUMN IF NOT EXISTS x_moh647_flow varchar;
        """
    )
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.ampath_billing.hooks import ensure_external_transit_locations

    ensure_external_transit_locations(env)
    _logger.info(
        'ampath_billing 1.0.84: ensured x_ampath_external_transit / x_moh647_flow '
        'and external-facility transit locations'
    )
