import logging
import csv
import os

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_BRAND_COLOR = "#135C33"
_BASE_COMPANY_CSV = "/mnt/odoo_config/company/res.company.csv"


def _read_base_logo_from_initializer():
    if not os.path.exists(_BASE_COMPANY_CSV):
        return None
    with open(_BASE_COMPANY_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    logo = (rows[0].get("logo") or "").strip()
    return logo or None


def _apply_base_company_branding(env):
    base_company = env.ref("base.main_company", raise_if_not_found=False)
    if not base_company:
        _logger.warning(
            "ampath_billing: base.main_company not found; branding hook skipped"
        )
        return

    updates = {
        "primary_color": _BRAND_COLOR,
        "secondary_color": _BRAND_COLOR,
        "email_primary_color": _BRAND_COLOR,
        "email_secondary_color": _BRAND_COLOR,
    }

    logo_b64 = _read_base_logo_from_initializer()
    if logo_b64:
        updates["logo"] = logo_b64

    base_company.sudo().write(updates)
    _logger.info(
        "ampath_billing: applied branding to base.main_company (id=%s)",
        base_company.id,
    )


def post_init_hook(env):
    if not isinstance(env, api.Environment):
        env = api.Environment(env, SUPERUSER_ID, {})
    _apply_base_company_branding(env)
