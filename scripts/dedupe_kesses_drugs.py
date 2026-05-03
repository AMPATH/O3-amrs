#!/usr/bin/env python3
"""Remove KESSES drug rows that duplicate ``drugs.csv`` (canonical drug list).

Compares using ``canonical_drug_key`` from ``product_name_canonical.py`` so
``AMOXICILLIN 500MG CAPSULES`` matches ``AMOXICILLIN 500mg CAP``.

Run from repo root::

    python3 scripts/dedupe_kesses_drugs.py

Rewrites only:

  - kesses_pharmaceuticals_stock.csv
  - kesses_oncology.csv
  - kesses_kemsa_stocks_received_latest.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from product_name_canonical import canonical_drug_key  # noqa: E402

VARIANT = ROOT / 'distro/config/odoo/initializer_config/product_variant'
DRUGS = VARIANT / 'drugs.csv'

KESSES_DRUG_FILES = [
    'kesses_pharmaceuticals_stock.csv',
    'kesses_oncology.csv',
    'kesses_kemsa_stocks_received_latest.csv',
]


def load_canonical_keys_from_drugs() -> set[str]:
    keys: set[str] = set()
    with DRUGS.open(newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            n = (row.get('name') or '').strip().strip('"')
            k = canonical_drug_key(n)
            if k:
                keys.add(k)
    return keys


def main() -> int:
    if not DRUGS.is_file():
        print('Missing', DRUGS, file=sys.stderr)
        return 1

    drug_keys = load_canonical_keys_from_drugs()
    print('Canonical keys from drugs.csv:', len(drug_keys))

    total_removed = 0
    total_kept = 0

    for fname in KESSES_DRUG_FILES:
        path = VARIANT / fname
        if not path.is_file():
            print(fname, '— skip (missing)')
            continue
        with path.open(newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            if not fieldnames:
                continue
            kept, removed = [], []
            for row in reader:
                n = (row.get('name') or '').strip().strip('"')
                k = canonical_drug_key(n)
                if k and k in drug_keys:
                    removed.append(n)
                else:
                    kept.append(row)
        with path.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            w.writeheader()
            w.writerows(kept)
        print(f'{fname}: removed {len(removed)} (kept {len(kept)})')
        for r in removed[:8]:
            print('  -', r[:70])
        if len(removed) > 8:
            print('  - ...', len(removed) - 8, 'more')
        total_removed += len(removed)
        total_kept += len(kept)

    print('Total removed (duplicates of drugs.csv):', total_removed)
    print('Total kept in kesses drug files:', total_kept)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
