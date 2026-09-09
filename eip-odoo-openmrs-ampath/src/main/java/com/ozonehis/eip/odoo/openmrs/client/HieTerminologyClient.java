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
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import lombok.extern.slf4j.Slf4j;
import org.openmrs.eip.EIPException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * HTTP client for {@code ${HIE_BASE_URL}/hie/api/v1/terminology-service}.
 *
 * <p>HIE UAT shapes:
 * <ul>
 *   <li>{@code /catalog}, {@code /product}, … — paginated with {@code page} (1-based) + {@code limit};
 *       payload under {@code Data.<resource>} (e.g. {@code Data.catalog}).
 *   <li>{@code /form}, {@code /unit}, {@code /route} — unpaginated; payload under {@code Data.forms}
 *       / {@code Data.units} / {@code Data.routes}.
 * </ul>
 */
@Slf4j
@Component
public class HieTerminologyClient {

    private static final String TERMINOLOGY_PATH = "/hie/api/v1/terminology-service";

    private static final Set<String> UNPAGINATED =
            Set.of("/form", "/unit", "/route", "form", "unit", "route");

    @Value("${hie.base.url:}")
    private String baseUrl;

    /** Cap catalog pages for local smoke tests (0 = no cap). */
    @Value("${eip.hie.product.sync.max.pages:0}")
    private int maxPages;

    @Autowired
    private HieAuthClient hieAuthClient;

    private final HttpClient httpClient = HttpClient.newHttpClient();
    private final ObjectMapper objectMapper = new ObjectMapper();

    public List<JsonNode> listAll(String relativePath) {
        String path = relativePath.startsWith("/") ? relativePath : "/" + relativePath;
        if (isUnpaginated(path)) {
            JsonNode response = getUrl(normalizeBase() + TERMINOLOGY_PATH + path);
            return extractItems(response, resourceKey(path));
        }

        List<JsonNode> all = new ArrayList<>();
        int page = 1;
        int limit = 100;
        Integer reportedPages = null;
        while (true) {
            if (maxPages > 0 && page > maxPages) {
                log.info("Stopping HIE {} fetch after maxPages={}", path, maxPages);
                break;
            }
            JsonNode response = get(path, page, limit);
            if (reportedPages == null) {
                reportedPages = extractPages(response);
            }
            List<JsonNode> pageItems = extractItems(response, resourceKey(path));
            if (pageItems.isEmpty()) {
                break;
            }
            all.addAll(pageItems);
            if (pageItems.size() < limit) {
                break;
            }
            if (reportedPages != null && page >= reportedPages) {
                break;
            }
            page++;
            if (page > 5000) {
                log.warn("Stopping HIE {} pagination after 5000 pages", path);
                break;
            }
        }
        return all;
    }

    public JsonNode get(String relativePath, int page, int limit) {
        String path = relativePath.startsWith("/") ? relativePath : "/" + relativePath;
        // HIE catalog pagination is 1-based; page=0 returns 422.
        String query = "page=" + Math.max(page, 1) + "&limit=" + limit;
        String url = normalizeBase() + TERMINOLOGY_PATH + path + "?" + query;
        return getUrl(url);
    }

    private JsonNode getUrl(String url) {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .header("Authorization", hieAuthClient.authorizationHeader())
                    .header("Accept", "application/json")
                    .GET()
                    .build();
            HttpResponse<String> response =
                    httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() >= 400) {
                throw new EIPException(
                        "HIE terminology GET failed (" + response.statusCode() + ") for " + redact(url)
                                + ": " + truncate(response.body()));
            }
            if (response.body() == null || response.body().isBlank()) {
                return objectMapper.createObjectNode();
            }
            return objectMapper.readTree(response.body());
        } catch (EIPException e) {
            throw e;
        } catch (Exception e) {
            throw new EIPException("HIE terminology request failed for " + redact(url), e);
        }
    }

    static List<JsonNode> extractItems(JsonNode response) {
        return extractItems(response, null);
    }

    static List<JsonNode> extractItems(JsonNode response, String preferredKey) {
        if (response == null || response.isNull()) {
            return Collections.emptyList();
        }
        if (response.isArray()) {
            List<JsonNode> items = new ArrayList<>();
            response.forEach(items::add);
            return items;
        }

        JsonNode data = response.has("Data")
                ? response.get("Data")
                : (response.has("data") ? response.get("data") : response);

        if (data != null && data.isArray()) {
            List<JsonNode> items = new ArrayList<>();
            data.forEach(items::add);
            return items;
        }

        List<String> keys = new ArrayList<>();
        if (preferredKey != null && !preferredKey.isBlank()) {
            keys.add(preferredKey);
        }
        keys.addAll(List.of(
                "catalog",
                "forms",
                "units",
                "routes",
                "products",
                "packages",
                "content",
                "data",
                "results",
                "items",
                "records"));

        for (String field : keys) {
            JsonNode arr = null;
            if (data != null && data.isObject() && data.has(field)) {
                arr = data.get(field);
            } else if (response.has(field)) {
                arr = response.get(field);
            }
            if (arr != null && arr.isArray()) {
                List<JsonNode> items = new ArrayList<>();
                arr.forEach(items::add);
                return items;
            }
        }
        return Collections.emptyList();
    }

    static Integer extractPages(JsonNode response) {
        if (response == null) {
            return null;
        }
        JsonNode data = response.has("Data") ? response.get("Data") : response.get("data");
        if (data != null && data.has("pages") && data.get("pages").canConvertToInt()) {
            return data.get("pages").asInt();
        }
        return null;
    }

    private static boolean isUnpaginated(String path) {
        return UNPAGINATED.contains(path) || UNPAGINATED.contains(path.toLowerCase(Locale.ROOT));
    }

    private static String resourceKey(String path) {
        String p = path.startsWith("/") ? path.substring(1) : path;
        return switch (p.toLowerCase(Locale.ROOT)) {
            case "catalog" -> "catalog";
            case "form" -> "forms";
            case "unit" -> "units";
            case "route" -> "routes";
            case "product" -> "products";
            case "package" -> "packages";
            default -> p;
        };
    }

    private String normalizeBase() {
        if (baseUrl == null || baseUrl.isBlank()) {
            throw new EIPException("hie.base.url / HIE_BASE_URL is not configured");
        }
        return baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl.trim();
    }

    private static String redact(String url) {
        int q = url.indexOf('?');
        return q > 0 ? url.substring(0, q) : url;
    }

    private static String truncate(String body) {
        if (body == null) {
            return "";
        }
        return body.length() > 300 ? body.substring(0, 300) + "…" : body;
    }
}
