# KEMSA Hospitals Tool → Odoo Product Match Summary

## Totals

- Excel products: **967**
- Matched (single CSV hit): **875**
- Ambiguous (multiple CSV hits): **13**
- Missing from product_variant: **79**
- CSV products not in Excel (informational): **818**

KEMSA codes are not stored in initializer CSVs today (`default_code` is empty).
The matched report includes `recommended_default_code` for a future import.

## Outcomes by Excel section

| Section | Total | Matched | Ambiguous | Missing |
|---------|------:|--------:|----------:|--------:|
| BASIC EQUIPMENT | 18 | 18 | 0 | 0 |
| CHV KITS | 3 | 3 | 0 | 0 |
| DENTAL PRODUCTS | 14 | 10 | 0 | 4 |
| EQUIPMENT | 9 | 7 | 0 | 2 |
| LAB PRODUCTS | 78 | 71 | 1 | 6 |
| LINEN PRODUCTS | 35 | 32 | 0 | 3 |
| NON-PHARMACEUTICALS | 209 | 204 | 1 | 4 |
| ONCOLOGY | 18 | 5 | 0 | 13 |
| ORTHOPAEDIC EQUIPMENT | 246 | 246 | 0 | 0 |
| OTHER | 2 | 0 | 0 | 2 |
| PHARMACEUTICALS | 271 | 256 | 11 | 4 |
| PUBLIC HEALTH PRODUCTS | 6 | 6 | 0 | 0 |
| RENAL | 10 | 10 | 0 | 0 |
| SSD PHARMACEUTICALS | 41 | 0 | 0 | 41 |
| X-RAY | 7 | 7 | 0 | 0 |

## Top missing categories

- 13 — ANTIHYPERTENSION MEDICINES
- 9 — ORAL HYPOGLYCAEMIC AGENTS
- 6 — MEDICINES FOR PSYCHOTIC DISORDERS
- 6 — CYTOTOXIC MEDICINES
- 5 — SEDATIVES/ANXIOLYTICS & ANTICONVULSANTS
- 4 — DENTAL CONSUMABLES
- 3 — ANTIACID/ANTIULCER MEDICINES
- 3 — IMMUNOMODULATORS
- 3 — TARGETED THERAPIES
- 3 — PROTECTIVE CLOTHING & GEAR
- 2 — VITAMINS AND MINERALS
- 2 — ANTIASTHMATICS AND DRUGS FOR COPD
- 2 — SAMPLE COLLECTION TUBES
- 2 — LABORATORY DIAGNOSTIC EQUIPMENT
- 1 — OPHTHALMIC ANTI-INFECTIVE MEDICINES

## CSV files with products not in Excel

- 599 — `drugs.csv`
- 58 — `kesses_pharmaceuticals_stock.csv`
- 45 — `kesses_kemsa_stocks_received_latest.csv`
- 40 — `lab_tests.csv`
- 28 — `kesses_non_pharmaceuticals.csv`
- 25 — `procedures.csv`
- 13 — `xray.csv`
- 4 — `ultrasound.csv`
- 3 — `kesses_oncology.csv`
- 2 — `kesses_renal.csv`
- 1 — `consultation_orders.csv`

## Ambiguous rows (manual resolution needed)

- `PM06AML001` AMLODIPINE TABLET 5MG → 2 candidates
- `PM01AMX015` AMOXICILLIN DISPERSIBLE SCORED TAB 250MG  *** Tracer *** → 2 candidates
- `PM01CEF003` CEFIXIME TABLET 400MG → 2 candidates
- `PM12CLT001` CLOTRIMAZOLE CREAM  - 1%  *** Tracer *** → 2 candidates
- `PM06ENA001` ENALAPRIL TABLETS - 5MG  *** Tracer *** → 2 candidates
- `PM07LGN001` LIGNOCAINE HYDROCHLORIDE  INJECTION  - 2% → 2 candidates
- `PM10XYT001` OXYTOCIN INJECTION - 10 IU/ML  *** Tracer *** → 2 candidates
- `PM07PHB001` PHENOBARBITONE  INJECTION - 200MG/ML → 2 candidates
- `PM12SLV001` SILVER SULPHADIAZINE CREAM - 1% → 3 candidates
- `PM12SLV003` SILVER SULPHADIAZINE CREAM 1% → 3 candidates
- `PM12TET002` TETRACYCLINE EYE OINTMENT -1%  *** Tracer *** → 2 candidates
- `NM07GLV006` GLOVES  SURGEON -  SIZE 7.5  STERILE  *** Tracer *** → 2 candidates
- `EM03HAE003` HAEMOGLOBIN  MICROCUVETTES - DIASPECT  *** Tracer *** → 2 candidates
