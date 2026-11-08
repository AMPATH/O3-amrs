# -*- coding: utf-8 -*-

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.ampath_billing.hooks import apply_moh647_default_mappings

    apply_moh647_default_mappings(env)
    _logger.info('ampath_billing 1.0.72: applied MOH 647 default mappings')
