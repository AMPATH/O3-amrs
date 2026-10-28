# AMPATH fhir-odoo:
# - ChargeItemDefinition uses sales list_price (not cost standard_price)
# - InventoryItem/ChargeItemDefinition resolve HIE SKUs via x_openmrs_drug_uuid
# - InventoryItem?location=<OpenMRS location UUID> scopes qty to that company's warehouse
FROM mekomsolutions/fhir-odoo

USER root
WORKDIR /app

COPY overlays/ /tmp/overlays/

# Overlay patched sources onto the upstream tree that remains in this image, then rebuild.
RUN set -eux; \
    cp -a /tmp/overlays/. /app/; \
    MAPPER=fhir-odoo-mapper/src/main/java/com/ozonehis/fhir/odoo/mappers/ChargeItemDefinitionMapper.java; \
    grep -q 'getListPrice()' "$MAPPER"; \
    grep -q 'x_openmrs_drug_uuid' fhir-odoo-mapper/src/main/java/com/ozonehis/fhir/odoo/model/Product.java; \
    grep -q 'searchByOpenmrsDrugUuid' fhir-odoo/src/main/java/com/ozonehis/fhir/odoo/api/ProductService.java; \
    grep -q 'name = "location"' fhir-odoo/src/main/java/com/ozonehis/fhir/odoo/inventoryItem/InventoryItemResourceProvider.java; \
    mvn -q -DskipTests --batch-mode package; \
    cp fhir-odoo-app/target/fhir-odoo-app-*.jar /app/fhir-odoo.jar

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "fhir-odoo.jar"]
