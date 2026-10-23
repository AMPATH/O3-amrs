# -*- coding: utf-8 -*-

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.ampath_billing.hooks import configure_internal_transfer_lots

    configure_internal_transfer_lots(env)
    _logger.info('ampath_billing 1.0.79: enabled lot entry on Internal Transfers')
