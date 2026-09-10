# Drug / pharma CSVs disabled (HIE owns drug catalogue)

These product CSVs were moved out of `product_variant/` so Odoo Initializer no longer seeds drugs.

HIE product catalogue sync (EIP Camel route) upserts drug SKUs into Odoo.

Keep other `product_variant/*.csv` files (lab, procedures, consultations, equipment, etc.).

Do **not** put `*.csv` back under `product_variant/` unless intentionally reverting to CSV drug bootstrap.
