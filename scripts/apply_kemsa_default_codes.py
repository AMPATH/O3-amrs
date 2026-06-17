#!/usr/bin/env python3
"""Set ``default_code`` on matched Odoo initializer products from hospitals-tool report.

Reads ``reports/hospitals-tool-match/matched.csv`` and updates rows in
``distro/config/odoo/initializer_config/product_variant/*.csv`` by ``odoo_id``.

Run from repo root::

    python3 scripts/apply_kemsa_default_codes.py
    python3 scripts/apply_kemsa_default_codes.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATCHED_CSV = ROOT / 'reports/hospitals-tool-match/matched.csv'
VARIANT_DIR = ROOT / 'distro/config/odoo/initializer_config/product_variant'


def load_matches(path: Path) -> dict[tuple[str, str], str]:
    """Map (csv_file, odoo_id) -> kemsa default_code."""
    out: dict[tuple[str, str], str] = {}
    with path.open(newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            csv_file = (row.get('csv_file') or '').strip()
            odoo_id = (row.get('odoo_id') or '').strip().strip('"')
            code = (row.get('recommended_default_code') or row.get('kemsa_code') or '').strip()
            if not csv_file or not odoo_id or not code:
                continue
            key = (csv_file, odoo_id)
            if key in out and out[key] != code:
                print(
                    f'Warning: conflicting code for {odoo_id} in {csv_file}: '
                    f'{out[key]!r} vs {code!r}',
                    file=sys.stderr,
                )
            out[key] = code
    return out


def insert_default_code_field(fieldnames: list[str]) -> list[str]:
    if 'default_code' in fieldnames:
        return fieldnames
    if 'name' in fieldnames:
        idx = fieldnames.index('name') + 1
        return fieldnames[:idx] + ['default_code'] + fieldnames[idx:]
    return fieldnames + ['default_code']


def apply_to_file(path: Path, updates: dict[str, str], dry_run: bool) -> tuple[int, int]:
    with path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return 0, 0
        fieldnames = insert_default_code_field(list(reader.fieldnames))
        rows = list(reader)

    updated = 0
    skipped = 0
    for row in rows:
        row_id = (row.get('id') or '').strip().strip('"')
        if row_id not in updates:
            continue
        code = updates[row_id]
        existing = (row.get('default_code') or '').strip().strip('"')
        if existing and existing != code:
            print(
                f'Skip {path.name} {row_id}: existing default_code={existing!r}',
                file=sys.stderr,
            )
            skipped += 1
            continue
        if existing == code:
            continue
        row['default_code'] = code
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
    parser = argparse.ArgumentParser(description='Apply KEMSA default_code to initializer CSVs.')
    parser.add_argument('--matched', type=Path, default=MATCHED_CSV)
    parser.add_argument('--variant-dir', type=Path, default=VARIANT_DIR)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not args.matched.is_file():
        print(f'Matched report not found: {args.matched}', file=sys.stderr)
        return 1

    matches = load_matches(args.matched)
    by_file: dict[str, dict[str, str]] = defaultdict(dict)
    for (csv_file, odoo_id), code in matches.items():
        by_file[csv_file][odoo_id] = code

    total_updated = 0
    total_skipped = 0
    for csv_file in sorted(by_file):
        path = args.variant_dir / csv_file
        if not path.is_file():
            print(f'Warning: CSV not found: {path}', file=sys.stderr)
            continue
        updated, skipped = apply_to_file(path, by_file[csv_file], args.dry_run)
        total_updated += updated
        total_skipped += skipped
        action = 'Would update' if args.dry_run else 'Updated'
        print(f'{action} {updated} rows in {csv_file} ({skipped} skipped)')

    print(f'Total: {total_updated} updated, {total_skipped} skipped, {len(matches)} matches loaded')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
