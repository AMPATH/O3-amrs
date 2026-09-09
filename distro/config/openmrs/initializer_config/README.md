# OpenMRS Initializer — HIE Product Catalogue

Seed files for ConceptSource, empty concept sets, and dispensing-units GP override.

Fixed UUIDs (UUID5 DNS namespace):

| Entity | UUID |
|---|---|
| ConceptSource `HIE Product Catalogue` | `c6a0fc5b-9aed-5167-8933-514ac306e01c` |
| Concept set HIE Product Catalogue Drugs | `2b52fc85-b59f-5e7f-a47d-d83863ac791f` |
| Concept set HIE Product Catalogue Dispensing Units | `0c9a8c3e-3220-553d-8111-9cbe021aafc7` |

These files are copied into `target/sdk-distro/web/openmrs_config` during `distro` Maven `package` (after `content.amrs` is unpacked), so Initializer loads them before EIP catalogue sync runs.

EIP env defaults match these UUIDs / the ConceptSource name.
