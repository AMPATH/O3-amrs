/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.handlers.openmrs;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.CodeableConcept;
import org.hl7.fhir.r4.model.Coding;
import org.hl7.fhir.r4.model.Condition;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * Loads active encounter diagnoses from OpenMRS FHIR (Condition) for SHA claim bundles.
 * Mirrors the intent of {@code HieService.Diagnosis} in ampath-sha-claims without AMRS SQL.
 */
@Slf4j
@Component
public class EncounterDiagnosisFhirHandler {

    @Autowired
    private IGenericClient openmrsFhirClient;

    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * @return JSON array string {@code [{"code":"...","display":"..."}, ...]} or {@code null} if none / error
     */
    public String buildDiagnosesJson(String encounterUuid) {
        if (encounterUuid == null || encounterUuid.isBlank()) {
            return null;
        }
        try {
            Bundle bundle = openmrsFhirClient
                    .search()
                    .forResource(Condition.class)
                    .where(Condition.ENCOUNTER.hasId(encounterUuid))
                    .count(100)
                    .returnBundle(Bundle.class)
                    .execute();

            List<Map<String, String>> rows = new ArrayList<>();
            if (bundle != null && bundle.hasEntry()) {
                for (Bundle.BundleEntryComponent entry : bundle.getEntry()) {
                    if (entry.hasResource() && entry.getResource() instanceof Condition) {
                        Condition c = (Condition) entry.getResource();
                        if (!c.hasCode()) {
                            continue;
                        }
                        Map<String, String> picked = pickCoding(c.getCode());
                        if (picked != null && !picked.get("code").isBlank()) {
                            rows.add(picked);
                        }
                    }
                }
            }
            return objectMapper.writeValueAsString(rows);
        } catch (Exception e) {
            log.warn(
                    "Could not load FHIR Conditions for encounter {}: {}",
                    encounterUuid,
                    e.getMessage());
            return null;
        }
    }

    private static Map<String, String> pickCoding(CodeableConcept concept) {
        Coding preferred = null;
        Coding fallback = null;
        for (Coding coding : concept.getCoding()) {
            if (!coding.hasCode() || coding.getCode().isBlank()) {
                continue;
            }
            if (fallback == null) {
                fallback = coding;
            }
            String sys = coding.hasSystem() ? coding.getSystem().toLowerCase(Locale.ROOT) : "";
            if (sys.contains("icd-11") || sys.contains("icd11")) {
                preferred = coding;
                break;
            }
        }
        Coding use = preferred != null ? preferred : fallback;
        if (use == null) {
            return null;
        }
        Map<String, String> m = new HashMap<>();
        m.put("code", use.getCode());
        m.put("display", use.hasDisplay() ? use.getDisplay() : use.getCode());
        return m;
    }
}
