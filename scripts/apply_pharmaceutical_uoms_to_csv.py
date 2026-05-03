#!/usr/bin/env python3
"""Rewrite ``uom_id/id`` and ``uom_po_id/id`` from ``infer_pharmaceutical_uom(name)``."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from pharmaceutical_uom_rules import infer_pharmaceutical_uom  # noqa: E402


def patch_csv(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return 0
    keys = rows[0].keys()
    if "uom_id/id" not in keys or "name" not in keys:
        return 0
    changed = 0
    for row in rows:
        uom = infer_pharmaceutical_uom(row.get("name") or "")
        if row.get("uom_id/id") != uom or row.get("uom_po_id/id") != uom:
            row["uom_id/id"] = uom
            row["uom_po_id/id"] = uom
            changed += 1
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(keys), quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "csv",
        nargs="*",
        type=Path,
        default=[
            ROOT / "distro/config/odoo/initializer_config/product_variant/kesses_pharmaceuticals_stock.csv",
            ROOT / "distro/config/odoo/initializer_config/product_variant/kesses_oncology.csv",
            ROOT / "distro/config/odoo/initializer_config/product_variant/kesses_kemsa_stocks_received_latest.csv",
        ],
        help="Product variant CSV paths (default: Kesses drug CSVs)",
    )
    args = ap.parse_args()
    total = 0
    for p in args.csv:
        if not p.is_file():
            print("skip (missing):", p, file=sys.stderr)
            continue
        n = patch_csv(p)
        total += n
        print(f"{p.name}: updated {n} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
