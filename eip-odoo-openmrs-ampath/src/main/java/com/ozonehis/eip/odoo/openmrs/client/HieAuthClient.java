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
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.stream.Collectors;
import lombok.extern.slf4j.Slf4j;
import org.openmrs.eip.EIPException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * OAuth2 client-credentials token client for Kenya HIE (same pattern as hie-saf).
 * Caches the access token and refreshes before expiry.
 */
@Slf4j
@Component
public class HieAuthClient {

    private static final long SKEW_SECONDS = 60;

    @Value("${hie.auth.url:}")
    private String authUrl;

    @Value("${hie.client.id:}")
    private String clientId;

    @Value("${hie.client.secret:}")
    private String clientSecret;

    @Value("${hie.grant.type:client_credentials}")
    private String grantType;

    @Value("${hie.test.bearer.token:}")
    private String testBearerToken;

    private final HttpClient httpClient = HttpClient.newHttpClient();
    private final ObjectMapper objectMapper = new ObjectMapper();

    private String cachedToken;
    private Instant expiresAt = Instant.EPOCH;

    /** Returns a usable Bearer access token (without the {@code Bearer } prefix). */
    public synchronized String getAccessToken() {
        if (testBearerToken != null && !testBearerToken.isBlank()) {
            return testBearerToken.trim();
        }
        if (cachedToken != null && Instant.now().isBefore(expiresAt.minusSeconds(SKEW_SECONDS))) {
            return cachedToken;
        }
        return fetchAndCacheToken();
    }

    public String authorizationHeader() {
        return "Bearer " + getAccessToken();
    }

    private String fetchAndCacheToken() {
        if (authUrl == null || authUrl.isBlank()) {
            throw new EIPException("hie.auth.url / HIE_AUTH_URL is not configured");
        }
        if (clientId == null || clientId.isBlank() || clientSecret == null || clientSecret.isBlank()) {
            throw new EIPException("HIE_CLIENT_ID and HIE_CLIENT_SECRET are required for catalogue sync");
        }

        try {
            Map<String, String> form = new LinkedHashMap<>();
            form.put("grant_type", grantType == null || grantType.isBlank() ? "client_credentials" : grantType);
            form.put("client_id", clientId);
            form.put("client_secret", clientSecret);
            String body = form.entrySet().stream()
                    .map(e -> URLEncoder.encode(e.getKey(), StandardCharsets.UTF_8)
                            + "="
                            + URLEncoder.encode(e.getValue(), StandardCharsets.UTF_8))
                    .collect(Collectors.joining("&"));

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(authUrl.trim()))
                    .header("Content-Type", "application/x-www-form-urlencoded")
                    .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                    .build();

            HttpResponse<String> response =
                    httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() >= 400) {
                throw new EIPException(
                        "HIE token request failed with status " + response.statusCode() + " (body omitted)");
            }

            JsonNode json = objectMapper.readTree(response.body());
            if (!json.hasNonNull("access_token")) {
                throw new EIPException("HIE token response missing access_token");
            }
            cachedToken = json.get("access_token").asText();
            long expiresIn = json.has("expires_in") ? json.get("expires_in").asLong(3600) : 3600;
            expiresAt = Instant.now().plusSeconds(Math.max(expiresIn, 60));
            log.info("HIE OAuth token acquired (expires_in={}s)", expiresIn);
            return cachedToken;
        } catch (EIPException e) {
            throw e;
        } catch (Exception e) {
            throw new EIPException("Failed to obtain HIE access token", e);
        }
    }
}
