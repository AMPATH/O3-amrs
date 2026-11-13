# -*- coding: utf-8 -*-

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.ampath_billing.hooks import ensure_department_locations

    # Allow legacy vouchers without destination while new UI requires it.
    cr.execute(
        """
        ALTER TABLE ampath_department_issue
            ALTER COLUMN department_id DROP NOT NULL;
        """
    )
    ensure_department_locations(env)
    _logger.info(
        'ampath_billing 1.0.85: department locations seeded; '
        'department_id nullable on ampath.department.issue'
    )
