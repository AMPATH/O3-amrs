#!/usr/bin/env python3
"""Enable lot tracking and expiry dates on stockable initializer products.

Sets ``tracking=lot`` and ``use_expiration_date=True`` on rows where ``type`` is
``product`` in ``distro/config/odoo/initializer_config/product_variant/*.csv``.

Service products (lab tests, procedures, etc.) are left unchanged.

Run from repo root::

    python3 scripts/enable_product_lots_expiry.py
    python3 scripts/enable_product_lots_expiry.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VARIANT_DIR = ROOT / 'distro/config/odoo/initializer_config/product_variant'

TRACKING = 'lot'
USE_EXPIRATION = 'True'


def insert_fields(fieldnames: list[str]) -> list[str]:
    out = list(fieldnames)
    if 'tracking' not in out:
        if 'type' in out:
            idx = out.index('type') + 1
            out.insert(idx, 'tracking')
        else:
            out.append('tracking')
    if 'use_expiration_date' not in out:
        if 'tracking' in out:
            idx = out.index('tracking') + 1
            out.insert(idx, 'use_expiration_date')
        else:
            out.append('use_expiration_date')
    return out


def process_file(path: Path, dry_run: bool) -> tuple[int, int]:
    with path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return 0, 0
        fieldnames = insert_fields(list(reader.fieldnames))
        rows = list(reader)

    updated = 0
    skipped = 0
    for row in rows:
        ptype = (row.get('type') or '').strip().lower()
        if ptype != 'product':
            skipped += 1
            continue
        changed = False
        if (row.get('tracking') or '').strip().lower() != TRACKING:
            row['tracking'] = TRACKING
            changed = True
        if (row.get('use_expiration_date') or '').strip().lower() not in ('true', '1'):
            row['use_expiration_date'] = USE_EXPIRATION
            changed = True
        if changed:
            updated += 1

    if updated and not dry_run:
        with path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(
                f, fieldnames=fieldnames, extrasaction='ignore', quoting=csv.QUOTE_ALL
            )
            writer.writeheader()
            writer.writerows(rows)

    return updated, skipped


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Enable lot tracking and expiry on stockable initializer products.'
    )
    parser.add_argument('--variant-dir', type=Path, default=VARIANT_DIR)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not args.variant_dir.is_dir():
        print(f'Variant dir not found: {args.variant_dir}', file=sys.stderr)
        return 1

    total_updated = 0
    total_skipped = 0
    for path in sorted(args.variant_dir.glob('*.csv')):
        updated, skipped = process_file(path, args.dry_run)
        total_updated += updated
        total_skipped += skipped
        if updated:
            action = 'Would update' if args.dry_run else 'Updated'
            print(f'{action} {updated} rows in {path.name} ({skipped} non-product rows)')

    action = 'Would update' if args.dry_run else 'Updated'
    print(f'{action} {total_updated} stockable products total ({total_skipped} service/other rows skipped)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
