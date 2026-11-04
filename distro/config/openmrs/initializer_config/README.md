# OpenMRS Initializer — HIE Product Catalogue + Medical Supplies

Seed files for ConceptSource, concept sets, medical-supply orderables, and dispensing-units GP override.
Place files **directly** under the domain folders (same layout as AMRS content):

| Path |
|---|
| `concepts/hie_product_catalogue_sets.csv` |
| `concepts/medical_supplies_concepts.csv` |
| `concepts/medical_supplies_set.csv` |
| `conceptsources/hie_product_catalogue.csv` |
| `globalproperties/hie-drugorder-properties.xml` |

Fixed UUIDs (UUID5 DNS namespace):

| Entity | UUID |
|---|---|
| ConceptSource `HIE Product Catalogue` | `c6a0fc5b-9aed-5167-8933-514ac306e01c` |
| Concept set HIE Product Catalogue Drugs | `2b52fc85-b59f-5e7f-a47d-d83863ac791f` |
| Concept set HIE Product Catalogue Dispensing Units | `0c9a8c3e-3220-553d-8111-9cbe021aafc7` |
| Concept set Medical Supplies (SPA orderableConceptSets) | `c6f16618-d618-49dc-9a5a-b5aef140d02c` |

Medical supply concepts use the same UUID as the matching Odoo Materials product xml id (`init.<uuid>` → concept `<uuid>`) so EIP `SupplyRequest` can resolve `ir.model.data` by name.

These files are copied into `target/sdk-distro/web/openmrs_config` during `distro` Maven `package`, after `openmrs-sdk:build-distro` runs in `prepare-package`, so Initializer loads them before EIP catalogue sync runs.

EIP env defaults match these UUIDs / the ConceptSource name.
