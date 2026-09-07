/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.routes;

import static org.openmrs.eip.fhir.Constants.HEADER_FHIR_EVENT_TYPE;
import static org.openmrs.eip.fhir.Constants.PROP_EVENT_OPERATION;

import com.ozonehis.eip.odoo.openmrs.processors.MedicationDispenseProcessor;
import lombok.Setter;
import org.apache.camel.LoggingLevel;
import org.apache.camel.builder.RouteBuilder;
import org.hl7.fhir.r4.model.MedicationDispense;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * Listens for OpenMRS {@code medication_dispense} DB events and syncs completed dispenses to Odoo stock.
 *
 * <p>camel-openmrs-fhir 4.2.0 has no MedicationDispense FhirResource, so this route is registered
 * directly as a {@code db-event.destinations} endpoint (see application.properties /
 * docker-compose).
 */
@Setter
@Component
public class MedicationDispenseRouting extends RouteBuilder {

    public static final String DB_EVENT_ENDPOINT = "direct:medication-dispense-to-stock";

    @Autowired
    private MedicationDispenseProcessor medicationDispenseProcessor;

    @Override
    public void configure() {
        // spotless:off
        from(DB_EVENT_ENDPOINT)
                .routeId("medication-dispense-db-event")
                .filter(simple("${exchangeProperty.event.snapshot} == false"))
                .filter(simple("${exchangeProperty.event.tableName} == 'medication_dispense'"))
                .log(LoggingLevel.INFO, "Processing medication_dispense DB event ${exchangeProperty.event.identifier}")
                .choice()
                    .when(simple("${exchangeProperty.event.operation} == 'd'"))
                        .setHeader(HEADER_FHIR_EVENT_TYPE, constant("d"))
                        .setBody(simple("${exchangeProperty.event.identifier}"))
                        .to("direct:medication-dispense-to-stock-processor")
                    .otherwise()
                        .toD("sql:SELECT voided FROM medication_dispense WHERE uuid = '${exchangeProperty.event.identifier}'?dataSource=#openmrsDataSource")
                        .choice()
                            .when(simple("${body.size()} == 0 || ${body[0]['voided']} == 1"))
                                .setHeader(HEADER_FHIR_EVENT_TYPE, constant("d"))
                                .setBody(simple("${exchangeProperty.event.identifier}"))
                                .to("direct:medication-dispense-to-stock-processor")
                            .otherwise()
                                .toD("fhir:read/resourceById?resourceClass=MedicationDispense&stringId=${exchangeProperty.event.identifier}")
                                .filter(body().isNotNull())
                                .filter(exchange -> exchange.getMessage().getBody() instanceof MedicationDispense)
                                .setHeader(HEADER_FHIR_EVENT_TYPE, simple("${exchangeProperty." + PROP_EVENT_OPERATION + "}"))
                                .to("direct:medication-dispense-to-stock-processor")
                        .endChoice()
                .end();

        from("direct:medication-dispense-to-stock-processor")
                .routeId("medication-dispense-to-stock-processor")
                .log(LoggingLevel.INFO, "Syncing MedicationDispense to Odoo stock")
                .process(medicationDispenseProcessor)
                .end();
        // spotless:on
    }
}
