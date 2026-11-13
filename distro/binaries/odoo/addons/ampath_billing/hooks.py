import logging
import csv
import os

from odoo import SUPERUSER_ID, api

from .moh647_defaults import (
    MOH647_CODES_BY_SEQUENCE,
    MOH647_NAMES_BY_SEQUENCE,
    MOH647_UNMAPPED_SEQUENCES,
)

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


def apply_moh647_default_mappings(env):
    """Link tracers to products by default_code / exact name when still unmapped."""
    Tracer = env['ampath.moh647.tracer'].sudo()
    Product = env['product.product'].sudo()
    Mapping = env['ampath.moh647.tracer.product'].sudo()

    tracers = Tracer.search([])
    if not tracers:
        _logger.info('ampath_billing: no MOH 647 tracers to map yet')
        return

    linked = 0
    skipped_unmapped = 0
    for tracer in tracers:
        if tracer.sequence in MOH647_UNMAPPED_SEQUENCES:
            skipped_unmapped += 1
            continue
        if tracer.product_line_ids:
            continue

        products = Product.browse()
        for code in MOH647_CODES_BY_SEQUENCE.get(tracer.sequence) or []:
            found = Product.search([('default_code', '=', code)], limit=1)
            products |= found
        if not products:
            for name in MOH647_NAMES_BY_SEQUENCE.get(tracer.sequence) or []:
                found = Product.search([('name', '=ilike', name)], limit=1)
                if found:
                    products |= found
                    break
                # Fallback: ilike contains for long HIE SKU names
                found = Product.search([('name', 'ilike', name)], limit=1)
                if found:
                    products |= found
                    break

        for product in products:
            exists = Mapping.search(
                [
                    ('tracer_id', '=', tracer.id),
                    ('product_id', '=', product.id),
                ],
                limit=1,
            )
            if not exists:
                Mapping.create(
                    {
                        'tracer_id': tracer.id,
                        'product_id': product.id,
                    }
                )
                linked += 1

    _logger.info(
        'ampath_billing: MOH 647 default mappings linked=%s intentionally_unmapped=%s',
        linked,
        skipped_unmapped,
    )


def configure_internal_transfer_lots(env):
    env['stock.picking.type']._ampath_configure_internal_transfers()
    _logger.info('ampath_billing: configured Internal Transfers to use existing lots')


def ensure_external_transit_locations(env):
    Location = env['stock.location'].sudo()
    for company in env['res.company'].sudo().search([]):
        existing = Location.search(
            [
                ('company_id', '=', company.id),
                ('x_ampath_external_transit', '=', True),
            ],
            limit=1,
        )
        if existing:
            continue
        Location.create(
            {
                'name': 'External facilities',
                'usage': 'transit',
                'company_id': company.id,
                'x_ampath_external_transit': True,
            }
        )
        _logger.info(
            'ampath_billing: created external-facility transit location for %s',
            company.name,
        )


DEPARTMENT_LOCATION_NAMES = (
    'Lab',
    'Theatre',
    'Maternity',
    'Pharmacy ward',
    'Radiology',
    'MCH',
)


def ensure_department_locations(env):
    """Create Departments/<name> internal locations under each warehouse."""
    Location = env['stock.location'].sudo()
    Warehouse = env['stock.warehouse'].sudo()
    created = 0
    for warehouse in Warehouse.search([]):
        parent = warehouse.view_location_id
        if not parent:
            continue
        company = warehouse.company_id
        departments = Location.search(
            [
                ('name', '=', 'Departments'),
                ('location_id', '=', parent.id),
                ('company_id', '=', company.id),
                ('usage', '=', 'view'),
            ],
            limit=1,
        )
        if not departments:
            departments = Location.create(
                {
                    'name': 'Departments',
                    'usage': 'view',
                    'location_id': parent.id,
                    'company_id': company.id,
                }
            )
            created += 1
        for name in DEPARTMENT_LOCATION_NAMES:
            existing = Location.search(
                [
                    ('name', '=', name),
                    ('location_id', '=', departments.id),
                    ('company_id', '=', company.id),
                ],
                limit=1,
            )
            if existing:
                continue
            Location.create(
                {
                    'name': name,
                    'usage': 'internal',
                    'location_id': departments.id,
                    'company_id': company.id,
                }
            )
            created += 1
    _logger.info(
        'ampath_billing: ensured department locations (created=%s)',
        created,
    )


VACCINE_PRODUCT_NAME_FRAGMENTS = (
    'BCG',
    'OPV',
    'Measles',
    'Rubella',
    'Rotavirus',
    'Rota',
    'DPT-HepB',
    'Pentavalent',
    'Pneumococcal',
    'PCV',
    'TD Vaccine',
    'Tetanus',
    'Diphtheria',
    'IPV',
    'HPV',
    'Typhoid',
    'TCV',
    'Janssen',
    'J&J',
    'Pfizer',
    'Biontech',
    'Yellow Fever',
    'BCG Diluent',
    'OPV Dropper',
    'MR Diluent',
    'Rota vaccine dropper',
)


def ensure_vaccine_store_locations(env):
    """Create a Vaccine Store internal location under each warehouse view."""
    Location = env['stock.location'].sudo()
    Warehouse = env['stock.warehouse'].sudo()
    created = 0
    for warehouse in Warehouse.search([]):
        parent = warehouse.view_location_id
        if not parent:
            continue
        company = warehouse.company_id
        existing = Location.search(
            [
                ('x_ampath_vaccine_store', '=', True),
                ('location_id', 'child_of', parent.id),
                ('company_id', '=', company.id),
            ],
            limit=1,
        )
        if existing:
            continue
        Location.create(
            {
                'name': 'Vaccine Store',
                'usage': 'internal',
                'location_id': parent.id,
                'company_id': company.id,
                'x_ampath_vaccine_store': True,
            }
        )
        created += 1
    _logger.info(
        'ampath_billing: ensured vaccine store locations (created=%s)',
        created,
    )


def ensure_vaccine_product_category(env):
    Category = env['product.category'].sudo()
    categ = Category.search([('x_ampath_vaccine_category', '=', True)], limit=1)
    if not categ:
        categ = Category.create(
            {
                'name': 'Vaccines',
                'x_ampath_vaccine_category': True,
            }
        )
        _logger.info('ampath_billing: created Vaccines product category')
    return categ


def tag_vaccine_products(env):
    """Mark Annex 7–like products as vaccines and put them in Vaccines category."""
    Product = env['product.product'].sudo()
    categ = ensure_vaccine_product_category(env)
    tagged = 0
    for fragment in VACCINE_PRODUCT_NAME_FRAGMENTS:
        products = Product.search(
            [
                ('type', '=', 'product'),
                ('x_ampath_vaccine', '=', False),
                '|',
                ('name', 'ilike', fragment),
                ('default_code', 'ilike', fragment),
            ]
        )
        for product in products:
            vals = {'x_ampath_vaccine': True}
            if product.categ_id != categ:
                vals['categ_id'] = categ.id
            product.write(vals)
            tagged += 1
    _logger.info('ampath_billing: tagged vaccine products count=%s', tagged)


def post_init_hook(env):
    if not isinstance(env, api.Environment):
        env = api.Environment(env, SUPERUSER_ID, {})
    _apply_base_company_branding(env)
    apply_moh647_default_mappings(env)
    configure_internal_transfer_lots(env)
    ensure_external_transit_locations(env)
    ensure_department_locations(env)
    ensure_vaccine_store_locations(env)
    tag_vaccine_products(env)
