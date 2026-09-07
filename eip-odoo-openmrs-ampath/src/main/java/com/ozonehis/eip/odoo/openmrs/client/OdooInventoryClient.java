/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.openmrs.eip.EIPException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class OdooInventoryClient {

    private static final String DISPENSE_PATH = "/ampath/inventory/dispense";
    private static final String REVERSE_PATH = "/ampath/inventory/reverse";

    @Value("${odoo.baseUrl}")
    private String baseUrl;

    @Value("${odoo.username}")
    private String username;

    @Value("${odoo.password}")
    private String password;

    private final HttpClient client = HttpClient.newHttpClient();
    private final ObjectMapper objectMapper = new ObjectMapper();

    public JsonNode dispense(
            String openmrsDrugUuid,
            double quantity,
            String companyExternalId,
            String openmrsOrderId,
            String patientExternalId) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("openmrs_drug_uuid", openmrsDrugUuid);
        body.put("quantity", quantity);
        body.put("company_external_id", companyExternalId);
        if (openmrsOrderId != null && !openmrsOrderId.isBlank()) {
            body.put("openmrs_order_id", openmrsOrderId);
        }
        if (patientExternalId != null && !patientExternalId.isBlank()) {
            body.put("patient_external_id", patientExternalId);
        }
        return post(DISPENSE_PATH, body);
    }

    public JsonNode reverse(String openmrsOrderId) {
        Map<String, Object> body = Map.of("openmrs_order_id", openmrsOrderId);
        return post(REVERSE_PATH, body);
    }

    private JsonNode post(String path, Map<String, Object> body) {
        try {
            String json = objectMapper.writeValueAsString(body);
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(normalizeBaseUrl() + path))
                    .header("Content-Type", "application/json")
                    .header("login", username)
                    .header("password", password)
                    .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
                    .build();

            HttpResponse<String> response =
                    client.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            JsonNode node = objectMapper.readTree(response.body());
            if (response.statusCode() >= 400) {
                String error = node.has("error") ? node.get("error").asText() : response.body();
                throw new EIPException(
                        String.format("Odoo inventory %s failed (%d): %s", path, response.statusCode(), error));
            }
            log.info(
                    "Odoo inventory {} succeeded for order {}: {}",
                    path,
                    body.get("openmrs_order_id"),
                    response.body());
            return node;
        } catch (EIPException e) {
            throw e;
        } catch (Exception e) {
            throw new EIPException("Failed to call Odoo inventory API " + path, e);
        }
    }

    private String normalizeBaseUrl() {
        if (baseUrl == null || baseUrl.isBlank()) {
            throw new EIPException("odoo.baseUrl is not configured");
        }
        return baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
    }
}
