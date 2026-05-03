#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve OpenMRS **drug UUIDs** (``/ws/rest/v1/drug``) for product names.

This uses the **Drug** resource’s own ``uuid`` (the OpenMRS drug record), not the
underlying concept’s uuid. The concept is still returned in the mapping file
for cross-checks.

Default server: https://staging.ampath.or.ke/openmrs — requires auth (**Get Drugs**).

Environment::

    export OPENMRS_URL=https://staging.ampath.or.ke/openmrs
    export OPENMRS_USERNAME=...
    export OPENMRS_PASSWORD=...

Examples::

    python3 scripts/resolve_openmrs_drug_uuids.py \\
      --input distro/config/odoo/initializer_config/product_variant/drugs.csv \\
      --limit 20 --output /tmp/drug_map.csv

    python3 scripts/resolve_openmrs_drug_uuids.py \\
      --input .../drugs.csv --output /tmp/m.csv \\
      --write-products-csv /tmp/drugs_with_openmrs_drug_uuid.csv

See https://rest.openmrs.org/ (Drug resource).
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

_SIMPLIFY = re.compile(
    r'\b(\d+\s*(?:MG|MCG|ML|G)\b|TABLET|TABLETS|CAP|CAPS|TAB|INJ|INJECTION).*$',
    re.I,
)


def _norm(s: str) -> str:
    return " ".join(s.upper().split())


def _auth_header(user: str, password: str) -> str:
    raw = f"{user}:{password}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def get_json(
    base: str,
    path: str,
    params: dict,
    user: str,
    password: str,
    ctx: ssl.SSLContext,
):
    q = urllib.parse.urlencode(params, doseq=True)
    url = f"{base.rstrip('/')}{path}"
    if q:
        url = f"{url}?{q}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    if user and password:
        req.add_header("Authorization", _auth_header(user, password))
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            if not data.strip():
                return None
            return json.loads(data)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        sys.stderr.write(f"HTTP {e.code} {path}: {body[:500]}\n")
        return None


def search_drugs(
    base: str, query: str, user: str, password: str, ctx: ssl.SSLContext, limit: int = 25
) -> list[dict]:
    data = get_json(
        base,
        "/ws/rest/v1/drug",
        {
            "q": query[:200],
            "limit": str(limit),
            "v": "custom:(uuid,display,name,concept:(uuid,display))",
        },
        user,
        password,
        ctx,
    )
    if data is None:
        return []
    if isinstance(data, dict) and "results" in data:
        return list(data["results"])
    if isinstance(data, list):
        return data
    return []


def simplify_query(name: str) -> str:
    s = name.strip()
    s = _SIMPLIFY.sub("", s).strip()
    parts = s.split()
    if len(parts) > 10:
        s = " ".join(parts[:8])
    return s or name.strip()[:80]


def drug_label(drug: dict) -> str:
    if drug.get("display"):
        return str(drug["display"])
    n = drug.get("name")
    if isinstance(n, str):
        return n
    if isinstance(n, dict) and n.get("display"):
        return str(n["display"])
    return ""


def pick_best_drug(drugs: list[dict], original_name: str) -> dict | None:
    if not drugs:
        return None
    if len(drugs) == 1:
        return drugs[0]
    on = _norm(simplify_query(original_name))
    best = drugs[0]
    best_r = 0.0
    for d in drugs:
        label = _norm(drug_label(d))
        if not label:
            continue
        r = SequenceMatcher(None, on, label).ratio()
        # substring boost
        if on in label or label in on:
            r = max(r, 0.85)
        if r > best_r:
            best_r, best = r, d
    return best


def concept_from_drug(drug: dict) -> tuple[str, str]:
    con = drug.get("concept")
    if isinstance(con, dict):
        return (con.get("uuid") or "", con.get("display") or "")
    return ("", "")


def main() -> int:
    ap = argparse.ArgumentParser(description="Resolve OpenMRS drug UUIDs for CSV drug names")
    ap.add_argument("--input", type=Path, required=True, help="CSV with a name column")
    ap.add_argument("--output", type=Path, help="Mapping CSV path")
    ap.add_argument(
        "--write-products-csv",
        type=Path,
        metavar="CSV",
        help="Copy input and set x_openmrs_drug_uuid where a drug match was found",
    )
    ap.add_argument("--limit", type=int, default=0, help="Max rows (0 = all)")
    ap.add_argument("--sleep", type=float, default=0.15, help="Delay between HTTP calls")
    ap.add_argument("--base-url", default="", help="Override OPENMRS_URL")
    args = ap.parse_args()

    import os

    base = (args.base_url or os.environ.get("OPENMRS_URL") or "").strip().rstrip("/")
    if not base:
        base = "https://staging.ampath.or.ke/openmrs"
    user = (os.environ.get("OPENMRS_USERNAME") or os.environ.get("OPENMRS_USER") or "").strip()
    password = (os.environ.get("OPENMRS_PASSWORD") or "").strip()

    if not user or not password:
        sys.stderr.write(
            "Set OPENMRS_USERNAME and OPENMRS_PASSWORD. Unauthenticated calls get 401.\n"
        )
        return 1

    ctx = ssl.create_default_context()
    ping = get_json(base, "/ws/rest/v1/session", {}, user, password, ctx)
    if isinstance(ping, dict) and ping.get("authenticated") is False:
        sys.stderr.write("Session reports not authenticated — check credentials.\n")
        return 1

    rows_in: list[dict] = []
    with args.input.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if args.limit and i >= args.limit:
                break
            rows_in.append(row)

    mapping: list[dict] = []
    n_drug = 0
    for row in rows_in:
        name = (row.get("name") or "").strip().strip('"')
        if not name:
            continue
        q = simplify_query(name)
        drugs = search_drugs(base, q, user, password, ctx)
        chosen = pick_best_drug(drugs, name) if drugs else None
        drug_uuid = ""
        drug_display = ""
        concept_uuid = ""
        concept_display = ""
        if chosen:
            drug_uuid = (chosen.get("uuid") or "").strip()
            drug_display = drug_label(chosen)
            concept_uuid, concept_display = concept_from_drug(chosen)
            if drug_uuid:
                n_drug += 1
        mapping.append(
            {
                "product_name": name,
                "search_query": q,
                "openmrs_drug_uuid": drug_uuid,
                "openmrs_drug_display": drug_display,
                "openmrs_concept_uuid": concept_uuid,
                "openmrs_concept_display": concept_display,
            }
        )
        time.sleep(args.sleep)

    if args.output:
        with args.output.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "product_name",
                    "search_query",
                    "openmrs_drug_uuid",
                    "openmrs_drug_display",
                    "openmrs_concept_uuid",
                    "openmrs_concept_display",
                ],
            )
            w.writeheader()
            w.writerows(mapping)
        print(f"Wrote {len(mapping)} rows to {args.output} ({n_drug} with drug UUID)")

    if args.write_products_csv:
        by_name = {m["product_name"]: m["openmrs_drug_uuid"] for m in mapping if m["openmrs_drug_uuid"]}
        out_rows: list[dict] = []
        with args.input.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fn = list(reader.fieldnames or [])
            if "x_openmrs_drug_uuid" not in fn:
                fn.append("x_openmrs_drug_uuid")
            for row in reader:
                n = (row.get("name") or "").strip().strip('"')
                du = by_name.get(n)
                if du:
                    row["x_openmrs_drug_uuid"] = du
                out_rows.append(row)
        with args.write_products_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fn, quoting=csv.QUOTE_ALL)
            w.writeheader()
            w.writerows(out_rows)
        print(f"Wrote {args.write_products_csv} with x_openmrs_drug_uuid where matched")

    if not args.output and not args.write_products_csv:
        for m in mapping[:15]:
            print(m)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
