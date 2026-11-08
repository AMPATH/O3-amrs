# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(
        'ampath_billing 1.0.82: MOH 647 A ignores inventory counts; '
        'B=Receipts; E/F=other facilities; D=scrap; G=on-hand at period end'
    )
