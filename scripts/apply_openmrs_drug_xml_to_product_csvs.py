#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Align initializer product ``id`` with OpenMRS drug UUIDs from drugs.xml.

For each row whose ``name`` matches a ``<display>`` in the XML (**case-insensitive**,
using Unicode ``casefold()``), sets only::

    id -> init.{drug_uuid}

The drug UUID is carried in the **id** (``init.<uuid>``), not a duplicate column.

Processes every ``*.csv`` under ``distro/config/odoo/initializer_config/product_variant``
that has ``id`` and ``name`` columns (skips others).

Strips ``x_openmrs_drug_uuid`` from headers/rows if present (initializer uses ``id``).
"""
from __future__ import annotations

import argparse
import csv
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def load_display_to_uuid(xml_path: Path) -> dict[str, str]:
    """Map casefolded display string -> OpenMRS drug uuid (first wins on key collision)."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    out: dict[str, str] = {}
    for drug in root.findall(".//drug"):
        u_el = drug.find("uuid")
        d_el = drug.find("display")
        if u_el is None or d_el is None:
            continue
        uuid = (u_el.text or "").strip()
        disp = (d_el.text or "").strip()
        if not uuid or not disp:
            continue
        key = disp.casefold()
        if key not in out:
            out[key] = uuid
    return out


def process_csv(path: Path, display_to_uuid: dict[str, str]) -> tuple[int, int]:
    """Returns (rows_total, rows_matched_xml)."""
    with path.open(newline="", encoding="utf-8") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        fieldnames = reader.fieldnames
        if not fieldnames or "id" not in fieldnames or "name" not in fieldnames:
            return (0, 0)
        fieldnames = [c for c in fieldnames if c != "x_openmrs_drug_uuid"]
        rows = list(reader)

    matched = 0
    for row in rows:
        row.pop("x_openmrs_drug_uuid", None)
        name = (row.get("name") or "").strip()
        name_key = name.casefold()
        if name_key in display_to_uuid:
            u = display_to_uuid[name_key]
            row["id"] = f"init.{u}"
            matched += 1

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)

    return (len(rows), matched)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--xml",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "drugs.xml",
        help="OpenMRS drug list XML (default: repo root drugs.xml)",
    )
    ap.add_argument(
        "--product-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "distro/config/odoo/initializer_config/product_variant",
        help="Directory containing product *.csv files",
    )
    args = ap.parse_args()

    if not args.xml.is_file():
        print(f"Missing XML: {args.xml}", file=sys.stderr)
        return 1

    display_to_uuid = load_display_to_uuid(args.xml)
    print(f"Loaded {len(display_to_uuid)} drugs from {args.xml}")

    if not args.product_dir.is_dir():
        print(f"Missing directory: {args.product_dir}", file=sys.stderr)
        return 1

    csv_paths = sorted(args.product_dir.glob("*.csv"))
    total_matched = 0
    for p in csv_paths:
        n, m = process_csv(p, display_to_uuid)
        if n == 0:
            print(f"  skip {p.name} (no id/name columns)")
            continue
        print(f"  {p.name}: rows={n} id_updates={m}")
        total_matched += m

    print(f"Done. Total rows with id set to init.{{drug_uuid}}: {total_matched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
