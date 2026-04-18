/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.handlers.openmrs;

import com.ozonehis.eip.odoo.openmrs.model.VisitAttributeSnapshot;
import java.util.Locale;
import lombok.extern.slf4j.Slf4j;
import org.hl7.fhir.r4.model.CodeType;
import org.hl7.fhir.r4.model.Encounter;
import org.hl7.fhir.r4.model.Extension;
import org.hl7.fhir.r4.model.StringType;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Reads OpenMRS visit-level attributes from the visit {@link Encounter} FHIR resource
 * (extensions whose URL contains the configured visit-attribute type UUIDs).
 */
@Slf4j
@Component
public class VisitAttributeHandler {

    @Autowired
    private EncounterHandler encounterHandler;

    @Value("${eip.visit.attribute.payment_method.uuid:}")
    private String paymentMethodAttributeUuid;

    @Value("${eip.visit.attribute.insurance_scheme.uuid:}")
    private String insuranceSchemeAttributeUuid;

    public VisitAttributeSnapshot readFromVisitEncounter(String visitEncounterUuid) {
        if (visitEncounterUuid == null || visitEncounterUuid.isBlank()) {
            return VisitAttributeSnapshot.empty();
        }
        try {
            Encounter visit = encounterHandler.getEncounterByEncounterID(visitEncounterUuid);
            return extractFromEncounter(visit);
        } catch (Exception e) {
            log.warn(
                    "Could not load visit encounter {} for billing visit attributes: {}",
                    visitEncounterUuid,
                    e.getMessage());
            return VisitAttributeSnapshot.empty();
        }
    }

    private VisitAttributeSnapshot extractFromEncounter(Encounter visit) {
        if (visit == null || !visit.hasExtension()) {
            return VisitAttributeSnapshot.empty();
        }
        String payment = null;
        String scheme = null;
        for (Extension ext : visit.getExtension()) {
            String url = ext.getUrl();
            if (url == null) {
                continue;
            }
            String lower = url.toLowerCase(Locale.ROOT);
            if (matchesUuid(lower, paymentMethodAttributeUuid)) {
                payment = firstNonBlank(payment, extractStringValue(ext));
            } else if (matchesUuid(lower, insuranceSchemeAttributeUuid)) {
                scheme = firstNonBlank(scheme, extractStringValue(ext));
            }
        }
        return new VisitAttributeSnapshot(payment, scheme);
    }

    private static String firstNonBlank(String current, String candidate) {
        if (current != null && !current.isBlank()) {
            return current;
        }
        return candidate;
    }

    private static boolean matchesUuid(String extensionUrlLower, String configuredUuid) {
        if (configuredUuid == null || configuredUuid.isBlank()) {
            return false;
        }
        return extensionUrlLower.contains(configuredUuid.toLowerCase(Locale.ROOT));
    }

    private static String extractStringValue(Extension ext) {
        if (!ext.hasValue()) {
            return null;
        }
        if (ext.getValue() instanceof StringType) {
            return ((StringType) ext.getValue()).getValue();
        }
        if (ext.getValue() instanceof CodeType) {
            return ((CodeType) ext.getValue()).getValue();
        }
        return ext.getValue().primitiveValue();
    }
}
