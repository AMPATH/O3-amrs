"""
Migration 1.0.5 → 1.0.6
Remove the `downpayment_line_id` field that was used by the old down-payment
flow. Partial invoicing via account.move is now used instead.
"""


def migrate(cr, version):
    # Remove the field record so Odoo does not try to reload it.
    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE model = 'sale.order.line'
          AND name = 'downpayment_line_id';
    """)

    # Drop the column if it still exists in the table.
    cr.execute("""
        ALTER TABLE sale_order_line
        DROP COLUMN IF EXISTS downpayment_line_id;
    """)

    # Remove any stale ir.model.data entries for this field.
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE model = 'ir.model.fields'
          AND name LIKE '%downpayment_line_id%';
    """)
