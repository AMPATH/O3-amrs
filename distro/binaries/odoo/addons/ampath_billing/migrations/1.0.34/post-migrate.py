import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Remove deprecated ``sale.order.line.x_intervention_code`` (use ``product.product`` only)."""
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sale_order_line' AND column_name = 'x_intervention_code'
        """
    )
    if cr.fetchone():
        cr.execute(
            'ALTER TABLE sale_order_line DROP COLUMN x_intervention_code'
        )
        _logger.info(
            'ampath_billing 1.0.34: dropped sale_order_line.x_intervention_code'
        )
