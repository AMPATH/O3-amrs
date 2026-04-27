"""
Migration 1.0.13 -> 1.0.14

Ensure the base company uses AMPATH branding values from our local setup.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_BRAND_COLOR = "#135C33"


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    base_company = env.ref("base.main_company", raise_if_not_found=False)
    if not base_company:
        _logger.warning(
            "ampath_billing 1.0.14: base.main_company not found; branding migration skipped"
        )
        return

    updates = {
        "primary_color": _BRAND_COLOR,
        "secondary_color": _BRAND_COLOR,
        "email_primary_color": _BRAND_COLOR,
        "email_secondary_color": _BRAND_COLOR,
    }

    # Reuse any already-imported branded logo (Kesses) to avoid hardcoding binary
    # payload in migration code.
    branded_company = env["res.company"].sudo().search(
        [("id", "!=", base_company.id), ("name", "=", "Kesses")], limit=1
    )
    if branded_company and branded_company.logo_web:
        updates["logo"] = branded_company.logo_web

    base_company.sudo().write(updates)
    _logger.info(
        "ampath_billing 1.0.14: enforced branding on base.main_company (id=%s)",
        base_company.id,
    )
