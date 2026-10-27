# Patched fhir-odoo: ChargeItemDefinition uses Odoo sales list_price (not cost).
# Build from ozone-his/fhir-odoo sources — mekomsolutions/fhir-odoo is a runtime JAR image.
# The same edit is recorded in patches/use-list-price.patch.
ARG FHIR_ODOO_REF=1.1.0

FROM maven:3.9-eclipse-temurin-17 AS build
ARG FHIR_ODOO_REF
WORKDIR /src
RUN curl -fsSL "https://github.com/ozone-his/fhir-odoo/archive/refs/tags/${FHIR_ODOO_REF}.tar.gz" \
    | tar xz --strip-components=1
RUN set -eux; \
    MAPPER=fhir-odoo-mapper/src/main/java/com/ozonehis/fhir/odoo/mappers/ChargeItemDefinitionMapper.java; \
    TEST=fhir-odoo-mapper/src/test/java/com/ozonehis/fhir/odoo/mappers/ChargeItemDefinitionMapperTest.java; \
    grep -q 'getStandardPrice()' "$MAPPER"; \
    sed -i 's/product\.getStandardPrice()/product.getListPrice()/g' "$MAPPER" "$TEST"; \
    grep -q 'getListPrice()' "$MAPPER"; \
    ! grep -q 'getStandardPrice()' "$MAPPER"
RUN mvn -q -DskipTests --batch-mode --no-transfer-progress package
RUN cp fhir-odoo-app/target/fhir-odoo-app-*.jar /tmp/fhir-odoo.jar

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /tmp/fhir-odoo.jar /app/fhir-odoo.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/fhir-odoo.jar"]
