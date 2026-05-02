import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Drop deprecated ``x_sha_preauth_required`` (pre-auth is driven only by ``x_intervention_code``)."""
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'product_product' AND column_name = 'x_sha_preauth_required'
        """
    )
    if cr.fetchone():
        cr.execute(
            'ALTER TABLE product_product DROP COLUMN x_sha_preauth_required'
        )
        _logger.info(
            'ampath_billing 1.0.33: dropped product_product.x_sha_preauth_required'
        )
