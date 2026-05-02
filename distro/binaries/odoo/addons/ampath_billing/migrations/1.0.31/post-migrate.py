import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Ensure DB column matches ``product.product.x_intervention_code`` (formerly ``x_sha_intervention_code``)."""
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'product_product'
          AND column_name IN ('x_sha_intervention_code', 'x_intervention_code')
        """
    )
    cols = {row[0] for row in cr.fetchall()}
    if 'x_sha_intervention_code' in cols and 'x_intervention_code' in cols:
        cr.execute(
            """
            UPDATE product_product
            SET x_intervention_code = COALESCE(
                NULLIF(BTRIM(COALESCE(x_intervention_code, '')), ''),
                x_sha_intervention_code
            )
            WHERE x_sha_intervention_code IS NOT NULL
              AND (x_intervention_code IS NULL OR BTRIM(x_intervention_code) = '')
            """
        )
        cr.execute(
            'ALTER TABLE product_product DROP COLUMN x_sha_intervention_code'
        )
        _logger.info(
            'ampath_billing 1.0.31: merged x_sha_intervention_code into x_intervention_code'
        )
    elif 'x_sha_intervention_code' in cols:
        cr.execute(
            """
            ALTER TABLE product_product
            RENAME COLUMN x_sha_intervention_code TO x_intervention_code
            """
        )
        _logger.info(
            'ampath_billing 1.0.31: renamed product_product.x_sha_intervention_code '
            'to x_intervention_code'
        )
