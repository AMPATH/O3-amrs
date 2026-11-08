# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(
        'ampath_billing 1.0.81: FEFO auto-pick for multi-SKU dispenses without lot_name'
    )
