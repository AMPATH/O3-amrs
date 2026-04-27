"""
1.0.10 → 1.0.11

`x_sha_intervention_code` is now declared on `product.product` in Python so the
initializer CSV import can populate it. Remove any duplicate *manual*
`ir.model.fields` row from older initializer-only setups, then backfill values.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_SHA_CODE_BY_TEMPLATE_NAME = {
    'Ultrasound abdomen': 'SHA-09-070',
}


def migrate(cr, version):
    cr.execute(
        """
        DELETE FROM ir_model_data d
        WHERE d.model = 'ir.model.fields'
          AND d.res_id IN (
              SELECT id FROM ir_model_fields
              WHERE name = 'x_sha_intervention_code'
                AND model = 'product.product'
          );
        DELETE FROM ir_model_fields
        WHERE name = 'x_sha_intervention_code'
          AND model = 'product.product';
        """
    )
    _logger.info(
        'ampath_billing 1.0.11: cleaned duplicate ir.model.fields (if any) for product.product.x_sha_intervention_code',
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    ProductTemplate = env['product.template'].sudo()
    for needle, code in _SHA_CODE_BY_TEMPLATE_NAME.items():
        templates = ProductTemplate.search([('name', 'ilike', needle)])
        for tmpl in templates:
            for variant in tmpl.product_variant_ids:
                if (variant.x_sha_intervention_code or '').strip():
                    continue
                variant.x_sha_intervention_code = code
                _logger.info(
                    'ampath_billing 1.0.11: set x_sha_intervention_code=%r on product.product id=%s',
                    code,
                    variant.id,
                )
