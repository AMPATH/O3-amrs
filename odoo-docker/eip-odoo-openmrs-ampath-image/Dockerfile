FROM mekomsolutions/eip-client

# CVE-2026-114938 (Java4Shell): Corretto 17 in the EIP client image. Do not switch this to -XX:UseAVX=2 (breaks arm64).
ENV JAVA_TOOL_OPTIONS="-XX:-UseBASE64Intrinsics"

# AMPATH customised EIP Odoo–OpenMRS (Ozone 2.2.0 base + synthetic ServiceRequest for extra order types).
# Drop-in alternative to stock eip-odoo-openmrs; order types via eip.order.type.uuids / env EIP_ORDER_TYPE_UUIDS.
COPY binaries/eip-odoo-openmrs-ampath-image/eip-odoo-openmrs-ampath-*.jar /eip-client/routes/
