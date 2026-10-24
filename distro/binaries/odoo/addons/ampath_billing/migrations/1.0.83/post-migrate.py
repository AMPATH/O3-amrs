# -*- coding: utf-8 -*-

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.ampath_billing.hooks import ensure_external_transit_locations

    ensure_external_transit_locations(env)
    _logger.info(
        'ampath_billing 1.0.83: department S11 + external E/F transit locations'
    )
