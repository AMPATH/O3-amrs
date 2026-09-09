/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.handlers.openmrs;

import static java.nio.charset.StandardCharsets.UTF_8;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ozonehis.eip.odoo.openmrs.client.OpenmrsRestClient;
import com.ozonehis.eip.odoo.openmrs.util.HieUuid;
import java.util.HashMap;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.openmrs.eip.EIPException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Creates HIE catalogue concepts and drugs in OpenMRS (never name-matches existing dictionary).
 */
@Slf4j
@Component
public class HieOpenmrsCatalogueWriter {

    private static final String SAME_AS = "SAME-AS";

    @Autowired
    private OpenmrsRestClient openmrsRestClient;

    @Value("${hie.product.catalogue.concept.source.name:HIE Product Catalogue}")
    private String conceptSourceName;

    @Value("${hie.product.catalogue.drug.concept.set.uuid:2b52fc85-b59f-5e7f-a47d-d83863ac791f}")
    private String drugConceptSetUuid;

    @Value("${hie.product.catalogue.dispensing.units.concept.set.uuid:0c9a8c3e-3220-553d-8111-9cbe021aafc7}")
    private String dispensingUnitsConceptSetUuid;

    private final ObjectMapper mapper = new ObjectMapper();
    private final Map<String, String> conceptSourceUuidCache = new HashMap<>();

    public String ensureFormConcept(String formCode, String formDescription) throws Exception {
        return ensureMappedConcept(HieUuid.forForm(formCode), formCode, formDescription, "Misc");
    }

    public String ensureUnitConcept(String unitCode, String unitDescription) throws Exception {
        // OpenMRS rejects duplicate concept names (e.g. CIEL already has "tablet").
        String label = unitDescription != null && !unitDescription.isBlank() ? unitDescription.trim() : unitCode;
        if (unitCode != null
                && !unitCode.isBlank()
                && label != null
                && !label.equalsIgnoreCase(unitCode)
                && !label.contains(unitCode)) {
            label = label + " (" + unitCode + ")";
        }
        String uuid = ensureMappedConcept(HieUuid.forUnit(unitCode), unitCode, label, "Units of Measure");
        addSetMember(dispensingUnitsConceptSetUuid, uuid);
        return uuid;
    }

    public String ensureRouteConcept(String routeCode, String routeDescription) throws Exception {
        return ensureMappedConcept(HieUuid.forRoute(routeCode), routeCode, routeDescription, "Misc");
    }

    public String upsertGeDrug(
            String geCode,
            String displayName,
            String strength,
            String formCode,
            String formDescription,
            boolean combination)
            throws Exception {
        String conceptUuid = ensureMappedConcept(HieUuid.forGe(geCode), geCode, displayName, "Drug");
        String dosageFormUuid = null;
        if (formCode != null && !formCode.isBlank()) {
            dosageFormUuid = ensureFormConcept(formCode, formDescription != null ? formDescription : formCode);
        }
        upsertDrug(conceptUuid, displayName, strength, dosageFormUuid, combination);
        addSetMember(drugConceptSetUuid, conceptUuid);
        return conceptUuid;
    }

    public void retireDrugIfExists(String geCode) throws Exception {
        String drugUuid = HieUuid.forGe(geCode);
        byte[] existing = openmrsRestClient.get("drug", drugUuid);
        if (existing != null) {
            openmrsRestClient.delete("drug", drugUuid);
            log.info("Retired OpenMRS drug {} for GE {}", drugUuid, geCode);
        }
    }

    private String ensureMappedConcept(String uuid, String code, String name, String conceptClass)
            throws Exception {
        byte[] existing = openmrsRestClient.get("concept", uuid);
        if (existing != null) {
            return uuid;
        }

        String sourceUuid = resolveConceptSourceUuid();
        String termUuid = createReferenceTerm(sourceUuid, code, name);

        ObjectNode body = mapper.createObjectNode();
        body.put("uuid", uuid);
        ArrayNode names = body.putArray("names");
        ObjectNode fsn = names.addObject();
        fsn.put("name", name != null && !name.isBlank() ? name : code);
        fsn.put("locale", "en");
        fsn.put("localePreferred", true);
        fsn.put("conceptNameType", "FULLY_SPECIFIED");
        // OpenMRS REST 2.x expects datatype/conceptClass as strings (not {display:...} maps).
        body.put("datatype", "N/A");
        body.put("conceptClass", conceptClass);
        ArrayNode mappings = body.putArray("mappings");
        ObjectNode map = mappings.addObject();
        map.putObject("conceptReferenceTerm").put("uuid", termUuid);
        map.put("conceptMapType", SAME_AS);

        openmrsRestClient.createOrUpdate("concept", null, mapper.writeValueAsString(body));
        log.info("Created OpenMRS concept {} ({}) code={}", name, uuid, code);
        return uuid;
    }

    private void upsertDrug(
            String conceptUuid, String name, String strength, String dosageFormUuid, boolean combination)
            throws Exception {
        String drugUuid = conceptUuid; // same UUID5 as GE concept
        ObjectNode body = mapper.createObjectNode();
        body.put("uuid", drugUuid);
        body.put("concept", conceptUuid);
        body.put("name", name);
        body.put("combination", combination);
        if (strength != null && !strength.isBlank()) {
            body.put("strength", strength);
        }
        if (dosageFormUuid != null) {
            body.put("dosageForm", dosageFormUuid);
        }

        byte[] existing = openmrsRestClient.get("drug", drugUuid);
        if (existing == null) {
            openmrsRestClient.createOrUpdate("drug", null, mapper.writeValueAsString(body));
            log.info("Created OpenMRS drug {} ({})", name, drugUuid);
        } else {
            openmrsRestClient.createOrUpdate("drug", drugUuid, mapper.writeValueAsString(body));
            log.debug("Updated OpenMRS drug {}", drugUuid);
        }
    }

    private String createReferenceTerm(String sourceUuid, String code, String name) throws Exception {
        String existingUuid = findReferenceTermUuid(sourceUuid, code);
        if (existingUuid != null) {
            return existingUuid;
        }

        ObjectNode body = mapper.createObjectNode();
        body.put("code", code);
        body.put("name", name != null && !name.isBlank() ? name : code);
        body.putObject("conceptSource").put("uuid", sourceUuid);
        try {
            byte[] created =
                    openmrsRestClient.createOrUpdate("conceptreferenceterm", null, mapper.writeValueAsString(body));
            JsonNode json = mapper.readTree(created);
            if (!json.hasNonNull("uuid")) {
                throw new EIPException("conceptreferenceterm create response missing uuid for code " + code);
            }
            return json.get("uuid").asText();
        } catch (EIPException e) {
            throw e;
        } catch (Exception e) {
            // Race / leftover term from a prior failed concept create
            String uuid = findReferenceTermUuid(sourceUuid, code);
            if (uuid != null) {
                log.info("Reusing existing concept reference term {} for code {}", uuid, code);
                return uuid;
            }
            throw e;
        }
    }

    private String findReferenceTermUuid(String sourceUuid, String code) throws Exception {
        String q = java.net.URLEncoder.encode(code, UTF_8);
        byte[] bytes = openmrsRestClient.get(
                "conceptreferenceterm?codeOrName=" + q + "&source=" + sourceUuid + "&v=default", null);
        if (bytes == null) {
            return null;
        }
        JsonNode root = mapper.readTree(bytes);
        JsonNode results = root.has("results") ? root.get("results") : root;
        if (!results.isArray()) {
            return null;
        }
        for (JsonNode node : results) {
            if (code.equalsIgnoreCase(node.path("code").asText())) {
                return node.path("uuid").asText(null);
            }
        }
        return null;
    }

    private void addSetMember(String setUuid, String memberUuid) throws Exception {
        if (setUuid == null || setUuid.isBlank() || memberUuid == null || memberUuid.isBlank()) {
            return;
        }
        byte[] setBytes = openmrsRestClient.get("concept", setUuid + "?v=custom:(uuid,setMembers:(uuid))");
        if (setBytes == null) {
            throw new EIPException("Concept set not found: " + setUuid);
        }
        JsonNode set = mapper.readTree(setBytes);
        if (set.has("setMembers")) {
            for (JsonNode member : set.get("setMembers")) {
                if (memberUuid.equals(member.path("uuid").asText())) {
                    return;
                }
            }
        }
        // OpenMRS REST: POST /concept/{setUuid} with setMembers including existing + new
        ObjectNode body = mapper.createObjectNode();
        ArrayNode members = body.putArray("setMembers");
        if (set.has("setMembers")) {
            for (JsonNode member : set.get("setMembers")) {
                members.add(member.path("uuid").asText());
            }
        }
        members.add(memberUuid);
        openmrsRestClient.createOrUpdate("concept", setUuid, mapper.writeValueAsString(body));
        log.info("Added concept {} to set {}", memberUuid, setUuid);
    }

    private synchronized String resolveConceptSourceUuid() throws Exception {
        if (conceptSourceUuidCache.containsKey(conceptSourceName)) {
            return conceptSourceUuidCache.get(conceptSourceName);
        }
        String q = java.net.URLEncoder.encode(conceptSourceName, UTF_8);
        byte[] bytes = openmrsRestClient.get("conceptsource?q=" + q + "&v=default", null);
        if (bytes == null) {
            throw new EIPException("ConceptSource not found: " + conceptSourceName);
        }
        JsonNode root = mapper.readTree(bytes);
        JsonNode results = root.has("results") ? root.get("results") : root;
        if (!results.isArray() || results.isEmpty()) {
            throw new EIPException(
                    "ConceptSource '" + conceptSourceName + "' missing — seed Initializer CSV before sync");
        }
        for (JsonNode node : results) {
            if (conceptSourceName.equalsIgnoreCase(node.path("display").asText())
                    || conceptSourceName.equalsIgnoreCase(node.path("name").asText())) {
                String uuid = node.get("uuid").asText();
                conceptSourceUuidCache.put(conceptSourceName, uuid);
                return uuid;
            }
        }
        String uuid = results.get(0).get("uuid").asText();
        conceptSourceUuidCache.put(conceptSourceName, uuid);
        return uuid;
    }
}
