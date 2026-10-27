# Patched fhir-odoo: ChargeItemDefinition uses Odoo sales list_price (not cost standard_price).
# Upstream mekomsolutions/fhir-odoo maps standard_price, so basket prices show seeded costs (e.g. 0.80).
FROM mekomsolutions/fhir-odoo

USER root
WORKDIR /app

# Prefer sed so we do not depend on patch(1) or exact upstream whitespace.
RUN set -eux; \
    MAPPER=fhir-odoo-mapper/src/main/java/com/ozonehis/fhir/odoo/mappers/ChargeItemDefinitionMapper.java; \
    TEST=fhir-odoo-mapper/src/test/java/com/ozonehis/fhir/odoo/mappers/ChargeItemDefinitionMapperTest.java; \
    grep -q 'getStandardPrice()' "$MAPPER"; \
    sed -i 's/product\.getStandardPrice()/product.getListPrice()/g' "$MAPPER" "$TEST"; \
    grep -q 'getListPrice()' "$MAPPER"; \
    ! grep -q 'getStandardPrice()' "$MAPPER"; \
    mvn -q -DskipTests --batch-mode package; \
    cp fhir-odoo-app/target/fhir-odoo-app-*.jar /app/fhir-odoo.jar

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "fhir-odoo.jar"]
