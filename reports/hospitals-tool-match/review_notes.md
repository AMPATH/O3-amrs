# Review Notes — Hospitals Tool Match

Generated as part of KEMSA hospitals tool matching (see `summary.md`).

## Ambiguous rows (13)

All ambiguous rows are **duplicate CSV entries** for the same canonical name across two KESSES files:

| Pattern | Count | Resolution |
|---------|------:|------------|
| `kesses_kemsa_stocks_received_latest.csv` vs `kesses_pharmaceuticals_stock.csv` | 10 | Prefer **`kesses_pharmaceuticals_stock.csv`** for hospital formulary; KEMSA received file is a stock overlay |
| `kesses_kemsa_stocks_received_latest.csv` vs `kesses_non_pharmaceuticals.csv` | 1 | Prefer **`kesses_non_pharmaceuticals.csv`** (NM07GLV006 gloves) |
| `kesses_kemsa_stocks_received_latest.csv` vs `kesses_lab_products.csv` | 1 | Prefer **`kesses_lab_products.csv`** (EM03HAE003) |
| Three-way duplicate in pharmaceuticals | 2 | PM12SLV001 / PM12SLV003 — pick one `kesses_pharmaceuticals_stock.csv` row; dedupe the duplicate `SILVER SULPHADIAZINE CREAM 1%` entry |

No true name collisions across unrelated products — safe to auto-resolve by file priority in a follow-up.

## Missing rows (79)

### By section

| Section | Missing | Notes |
|---------|--------:|-------|
| SSD PHARMACEUTICALS | 41 | **Entire SSD brand formulary** absent from initializer CSVs (e.g. Dapagliflozin, Empagliflozin, branded antihypertensives). Suggested file `kesses_pharmaceuticals_stock.csv` is correct. |
| ONCOLOGY | 13 | Cytotoxics, immunomodulators, targeted therapies (Abiraterone, Lenalidomide, Rituximab, Trastuzumab, etc.) not in `kesses_oncology.csv`. |
| PHARMACEUTICALS | 4 | Name normalization gaps (spacing/typos): e.g. `NORADRENALINEINJECTION` (no space), brand suffixes stripped differently. |
| NON-PHARMACEUTICALS | 4 | Long suture kit name, rehab consumable, autoclave tape — likely never imported from KESSES stock. |
| LAB PRODUCTS | 6 | Lab consumables/equipment not in `kesses_lab_products.csv`. |
| DENTAL PRODUCTS | 4 | Gutta-percha sizes and acrylic teeth sets. |
| LINEN PRODUCTS | 3 | Patient uniforms, gumboots, theatre clogs. |
| EQUIPMENT | 2 | Examination couch, oxygen concentrator. |
| OTHER | 2 | Excel section mislabeled — both are **pharmaceuticals** (dental lignocaine cart, valsartan combo). Should target `kesses_pharmaceuticals_stock.csv`, not `kesses_non_pharmaceuticals.csv`. |

### Section → CSV mapping validation

| Excel section | Suggested CSV | Valid? |
|---------------|---------------|--------|
| PHARMACEUTICALS, SSD PHARMACEUTICALS | `kesses_pharmaceuticals_stock.csv` | Yes |
| ONCOLOGY | `kesses_oncology.csv` | Yes |
| RENAL | `kesses_renal.csv` | Yes (0 missing) |
| NON-PHARMACEUTICALS | `kesses_non_pharmaceuticals.csv` | Yes |
| LAB PRODUCTS | `kesses_lab_products.csv` | Yes |
| LINEN PRODUCTS | `kesses_linen_products.csv` | Yes |
| X-RAY | `kesses_xray.csv` | Yes (0 missing) |
| DENTAL PRODUCTS | `kesses_dental_products.csv` | Yes |
| PUBLIC HEALTH PRODUCTS | `kesses_public_health.csv` | Yes (0 missing) |
| BASIC EQUIPMENT | `kesses_basic_equipment.csv` | Yes (0 missing) |
| EQUIPMENT | `kesses_equipments.csv` | Yes |
| CHV KITS | `kesses_chv.csv` | Yes (0 missing) |
| ORTHOPAEDIC EQUIPMENT | `kesses_orthopaedic.csv` | Yes (0 missing) |
| OTHER | `kesses_non_pharmaceuticals.csv` | **Partial** — 2/2 rows are drugs; use pharmaceuticals CSV instead |

See `missing_with_suggestions.csv` for token-overlap near-matches on the 4 PHARMACEUTICALS name-gap rows.

## CSV not in Excel (818)

Expected gap: `drugs.csv` (599 rows) is the OpenMRS drug catalog, not the KEMSA hospital ordering list. Remaining CSV-only rows are KESSES stock items and clinical services (lab tests, procedures, x-ray) outside the hospitals tool scope.

## KEMSA codes

No `default_code` values exist in initializer CSVs today. `matched.csv` includes `recommended_default_code` (= KEMSA code) for 875 products ready for a future bulk update.
