/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.processors;

import com.ozonehis.eip.odoo.openmrs.client.OdooInventoryClient;
import lombok.Setter;
import lombok.extern.slf4j.Slf4j;
import org.apache.camel.CamelExecutionException;
import org.apache.camel.Exchange;
import org.apache.camel.Processor;
import org.hl7.fhir.r4.model.Extension;
import org.hl7.fhir.r4.model.MedicationDispense;
import org.hl7.fhir.r4.model.Quantity;
import org.hl7.fhir.r4.model.Reference;
import org.hl7.fhir.r4.model.StringType;
import org.hl7.fhir.r4.model.Type;
import org.openmrs.eip.fhir.Constants;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * Syncs OpenMRS pharmacy dispenses to Odoo stock via the inventory HTTP API.
 *
 * <p>Inventory is updated only when a {@link MedicationDispense} is recorded (status
 * {@code completed}), not when a MedicationRequest / drug order is created.
 */
@Slf4j
@Setter
@Component
public class MedicationDispenseProcessor implements Processor {

    /** AMPATH FHIR extension for Odoo lot / batch name ({@code valueString}). */
    public static final String EXT_BATCH_NUMBER =
            "https://ampath.or.ke/fhir/StructureDefinition/medicationdispense-batch-number";

    @Autowired
    private OdooInventoryClient odooInventoryClient;

    @Override
    public void process(Exchange exchange) {
        try {
            String eventType = exchange.getMessage().getHeader(Constants.HEADER_FHIR_EVENT_TYPE, String.class);
            if (eventType == null) {
                throw new IllegalArgumentException("Event type not found in the exchange headers.");
            }

            // Delete events only carry the UUID; reverse any prior Odoo picking for that dispense.
            if ("d".equals(eventType)) {
                String dispenseId = resolveDispenseIdFromBody(exchange);
                log.info("Reversing Odoo stock for deleted MedicationDispense {}", dispenseId);
                odooInventoryClient.reverse(dispenseId);
                return;
            }

            MedicationDispense dispense = exchange.getMessage().getBody(MedicationDispense.class);
            if (dispense == null) {
                throw new IllegalArgumentException("Exchange body is not a MedicationDispense");
            }

            String dispenseId = dispense.getIdElement().getIdPart();
            log.debug(
                    "Processing MedicationDispense {} (status={}, event={})",
                    dispenseId,
                    dispense.getStatus(),
                    eventType);

            if (shouldReverse(dispense)) {
                log.info("Reversing Odoo stock for MedicationDispense {} (status={})", dispenseId, dispense.getStatus());
                odooInventoryClient.reverse(dispenseId);
                return;
            }

            if (!isCompleted(dispense)) {
                log.info(
                        "Skipping MedicationDispense {}: status {} is not completed",
                        dispenseId,
                        dispense.getStatus());
                return;
            }

            DispensePayload payload = buildDispensePayload(dispense);
            odooInventoryClient.dispense(
                    payload.openmrsDrugUuid(),
                    payload.quantity(),
                    payload.companyExternalId(),
                    dispenseId,
                    payload.patientExternalId(),
                    payload.lotName(),
                    payload.quantityUnitUuid());
        } catch (Exception e) {
            throw new CamelExecutionException("Error processing MedicationDispense", exchange, e);
        }
    }

    static boolean isCompleted(MedicationDispense dispense) {
        return dispense.getStatus() == MedicationDispense.MedicationDispenseStatus.COMPLETED;
    }

    static boolean shouldReverse(MedicationDispense dispense) {
        MedicationDispense.MedicationDispenseStatus status = dispense.getStatus();
        return status == MedicationDispense.MedicationDispenseStatus.CANCELLED
                || status == MedicationDispense.MedicationDispenseStatus.ENTEREDINERROR;
    }

    static DispensePayload buildDispensePayload(MedicationDispense dispense) {
        String drugUuid = resolveReferenceId(dispense.getMedicationReference(), "medication");
        String locationUuid = resolveReferenceId(dispense.getLocation(), "location");
        String patientUuid = resolveReferenceId(dispense.getSubject(), "subject/patient");
        double quantity = resolveQuantity(dispense);
        String lotName = resolveBatchNumber(dispense);
        String quantityUnitUuid = resolveQuantityUnitUuid(dispense);
        return new DispensePayload(drugUuid, quantity, locationUuid, patientUuid, lotName, quantityUnitUuid);
    }

    static double resolveQuantity(MedicationDispense dispense) {
        if (!dispense.hasQuantity()) {
            throw new IllegalArgumentException(
                    "MedicationDispense "
                            + dispense.getIdElement().getIdPart()
                            + " has no quantity");
        }
        Quantity quantity = dispense.getQuantity();
        if (quantity.getValue() == null || quantity.getValue().doubleValue() <= 0) {
            throw new IllegalArgumentException(
                    "MedicationDispense "
                            + dispense.getIdElement().getIdPart()
                            + " quantity must be greater than zero");
        }
        return quantity.getValue().doubleValue();
    }

    static String resolveQuantityUnitUuid(MedicationDispense dispense) {
        if (!dispense.hasQuantity()) {
            return null;
        }
        Quantity quantity = dispense.getQuantity();
        if (quantity.hasCode() && looksLikeUuid(quantity.getCode())) {
            return quantity.getCode();
        }
        // OpenMRS often puts concept uuid in system URL path or as code
        if (quantity.hasSystem()) {
            String system = quantity.getSystem();
            if (system.contains("/")) {
                String maybe = system.substring(system.lastIndexOf('/') + 1);
                if (looksLikeUuid(maybe)) {
                    return maybe;
                }
            }
        }
        return null;
    }

    static String resolveBatchNumber(MedicationDispense dispense) {
        Extension ext = dispense.getExtensionByUrl(EXT_BATCH_NUMBER);
        if (ext == null || !ext.hasValue()) {
            for (Extension e : dispense.getExtension()) {
                if (e.getUrl() != null
                        && e.getUrl().endsWith("medicationdispense-batch-number")
                        && e.hasValue()) {
                    ext = e;
                    break;
                }
            }
        }
        if (ext == null || !ext.hasValue()) {
            return null;
        }
        Type value = ext.getValue();
        if (value instanceof StringType stringType) {
            String batch = stringType.getValue();
            return batch != null && !batch.isBlank() ? batch.trim() : null;
        }
        String primitive = value.primitiveValue();
        return primitive != null && !primitive.isBlank() ? primitive.trim() : null;
    }

    static boolean looksLikeUuid(String value) {
        return value != null && value.matches("(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}");
    }

    static String resolveReferenceId(Reference reference, String fieldName) {
        if (reference == null || !reference.hasReference()) {
            throw new IllegalArgumentException("MedicationDispense has no " + fieldName + " reference");
        }
        String ref = reference.getReference();
        if (!ref.contains("/")) {
            throw new IllegalArgumentException("Invalid " + fieldName + " reference: " + ref);
        }
        return ref.split("/")[1];
    }

    private static String resolveDispenseIdFromBody(Exchange exchange) {
        Object body = exchange.getMessage().getBody();
        if (body instanceof MedicationDispense dispense) {
            return dispense.getIdElement().getIdPart();
        }
        if (body instanceof String id && !id.isBlank()) {
            return id.contains("/") ? id.substring(id.lastIndexOf('/') + 1) : id;
        }
        throw new IllegalArgumentException("Cannot resolve MedicationDispense id from exchange body: " + body);
    }

    record DispensePayload(
            String openmrsDrugUuid,
            double quantity,
            String companyExternalId,
            String patientExternalId,
            String lotName,
            String quantityUnitUuid) {}
}
