/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.processors;

import lombok.extern.slf4j.Slf4j;
import org.apache.camel.Exchange;
import org.apache.camel.Processor;
import org.hl7.fhir.r4.model.MedicationRequest;
import org.springframework.stereotype.Component;

/**
 * MedicationRequest events no longer update Odoo stock. Pharmacy stock is adjusted only when a
 * {@code MedicationDispense} is completed (see {@link MedicationDispenseProcessor}).
 *
 * <p>This processor is retained so {@code direct:fhir-medicationrequest} remains a safe no-op if
 * MedicationRequest is re-enabled in {@code eip.fhir.resources}.
 */
@Slf4j
@Component
public class MedicationRequestProcessor implements Processor {

    @Override
    public void process(Exchange exchange) {
        MedicationRequest request = exchange.getMessage().getBody(MedicationRequest.class);
        String id = request != null ? request.getIdElement().getIdPart() : "unknown";
        log.info(
                "Ignoring MedicationRequest {} for stock sync; Odoo inventory updates on MedicationDispense only",
                id);
    }
}
