FROM mekomsolutions/eip-client

# CVE-2026-114938 (Java4Shell): Corretto 17 in the EIP client image. Do not switch this to -XX:UseAVX=2 (breaks arm64).
ENV JAVA_TOOL_OPTIONS="-XX:-UseBASE64Intrinsics"

# Stock EIP Odoo–OpenMRS client image with bundled Camel routes.
# Only the stock JAR — AMPATH routes run in a separate container.
COPY binaries/eip-odoo-openmrs/eip-odoo-openmrs-*.jar /eip-client/routes/


