/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.handlers.openmrs;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ozonehis.eip.odoo.openmrs.client.OpenmrsRestClient;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * Loads visit diagnoses from OpenMRS REST /visit payload for the active quotation.
 * Uses encounter.diagnoses nested in visit representation and deduplicates by diagnosis code.
 */
@Slf4j
@Component
public class VisitDiagnosisRestHandler {

    @Autowired
    private OpenmrsRestClient openmrsRestClient;

    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * Diagnoses across a whole visit using OpenMRS REST:
     * {@code /ws/rest/v1/visit/{uuid}?v=custom:(encounters:(diagnoses:(...)))}.
     */
    public String buildDiagnosesJsonForVisit(String visitEncounterUuid) {
        if (visitEncounterUuid == null || visitEncounterUuid.isBlank()) {
            return null;
        }
        try {
            LinkedHashMap<String, Map<String, String>> byCode = new LinkedHashMap<>();
            mergeInto(byCode, collectDiagnosesForVisit(visitEncounterUuid));
            return objectMapper.writeValueAsString(new ArrayList<>(byCode.values()));
        } catch (Exception e) {
            log.warn(
                    "Could not build visit-wide diagnoses from REST for visit {}: {}",
                    visitEncounterUuid,
                    e.getMessage());
            return null;
        }
    }

    private static void mergeInto(LinkedHashMap<String, Map<String, String>> byCode, List<Map<String, String>> rows) {
        for (Map<String, String> row : rows) {
            String code = row.get("code");
            if (code != null && !code.isBlank()) {
                byCode.putIfAbsent(code, row);
            }
        }
    }

    private List<Map<String, String>> collectDiagnosesForVisit(String visitUuid) {
        List<Map<String, String>> rows = new ArrayList<>();
        try {
            String view =
                    "custom:(uuid,encounters:(uuid,diagnoses:(uuid,diagnosis:(coded:(uuid,display)),display,voided)))";
            String resource = "visit/" + visitUuid + "?v=" + view;
            byte[] payload = openmrsRestClient.get(resource, null);
            if (payload == null || payload.length == 0) {
                return rows;
            }
            JsonNode root = objectMapper.readTree(new String(payload, StandardCharsets.UTF_8));
            JsonNode encounters = root.path("encounters");
            if (!encounters.isArray()) {
                return rows;
            }
            for (JsonNode encounter : encounters) {
                JsonNode diagnoses = encounter.path("diagnoses");
                if (!diagnoses.isArray()) {
                    continue;
                }
                for (JsonNode dx : diagnoses) {
                    if (dx.path("voided").asBoolean(false)) {
                        continue;
                    }
                    JsonNode coded = dx.path("diagnosis").path("coded");
                    String code = text(coded.path("uuid"));
                    String display = text(coded.path("display"));
                    if (code == null) {
                        code = text(dx.path("uuid"));
                        if (code == null) {
                            continue;
                        }
                    }
                    if (display == null) {
                        display = text(dx.path("display"));
                    }
                    if (display == null) {
                        display = code;
                    }
                    Map<String, String> row = new LinkedHashMap<>();
                    row.put("code", code);
                    row.put("display", display);
                    rows.add(row);
                }
            }
        } catch (Exception e) {
            log.debug("REST visit diagnosis fetch failed for visit {}: {}", visitUuid, e.getMessage());
        }
        return rows;
    }

    private static String text(JsonNode node) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return null;
        }
        String t = node.asText();
        return t == null || t.isBlank() ? null : t;
    }
}
