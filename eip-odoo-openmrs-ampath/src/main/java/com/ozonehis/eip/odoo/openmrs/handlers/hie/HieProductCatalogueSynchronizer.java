/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.handlers.hie;

import com.fasterxml.jackson.databind.JsonNode;
import com.ozonehis.eip.odoo.openmrs.client.HieAuthClient;
import com.ozonehis.eip.odoo.openmrs.client.HieTerminologyClient;
import com.ozonehis.eip.odoo.openmrs.handlers.odoo.HieOdooCatalogueWriter;
import com.ozonehis.eip.odoo.openmrs.handlers.openmrs.HieOpenmrsCatalogueWriter;
import com.ozonehis.eip.odoo.openmrs.util.HieUuid;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * One full HIE catalogue sync run: auth → forms/units/routes → catalog → OpenMRS + Odoo.
 *
 * <p>Auth / terminology list failures abort the run. Per-item OpenMRS/Odoo write failures are
 * logged and skipped so one bad form/unit/GE does not stop the rest of the catalogue.
 */
@Slf4j
@Component
public class HieProductCatalogueSynchronizer {

    @Autowired
    private HieAuthClient hieAuthClient;

    @Autowired
    private HieTerminologyClient terminologyClient;

    @Autowired
    private HieOpenmrsCatalogueWriter openmrsWriter;

    @Autowired
    private HieOdooCatalogueWriter odooWriter;

    /**
     * When {@code > 0}, skip full form/unit/route prefetch (smoke tests). Catalog rows still
     * upsert forms/units on demand.
     */
    @Value("${eip.hie.product.sync.max.pages:0}")
    private int maxPages;

    public void sync() throws Exception {
        log.info("Starting HIE product catalogue sync (maxPages={})", maxPages);
        hieAuthClient.getAccessToken();

        AtomicInteger itemFailures = new AtomicInteger();

        Map<String, String> formNames;
        Map<String, String> unitNames;
        if (maxPages > 0) {
            log.info("Skipping full form/unit/route prefetch (maxPages={})", maxPages);
            formNames = Map.of();
            unitNames = Map.of();
        } else {
            formNames = safePrefetchForms(itemFailures);
            unitNames = safePrefetchUnits(itemFailures);
            safePrefetchRoutes(itemFailures);
        }

        List<JsonNode> catalog = terminologyClient.listAll("/catalog");
        log.info("Fetched {} HIE catalog rows", catalog.size());

        Set<String> activeGeCodes = new HashSet<>();
        Set<String> activePackageCodes = new HashSet<>();
        Map<String, Integer> activePackageCountByGe = new HashMap<>();
        // Cache HIE /product lookups for the run (key = GE|etcdProductId).
        Map<String, Optional<JsonNode>> productByGeAndEtcd = new HashMap<>();
        int skippedRows = 0;
        int archivedRows = 0;

        for (JsonNode row : catalog) {
            try {
                String status = text(row, "registration_status", "status", "reg_status");
                boolean active = status == null
                        || status.isBlank()
                        || "active".equalsIgnoreCase(status)
                        || "registered".equalsIgnoreCase(status);

                String geCode = text(row, "generic_concept_code", "ge_code", "GE", "generic_code");
                String packageCode = text(row, "package_code", "product_code", "ph_code", "code");
                if (geCode == null || geCode.isBlank() || packageCode == null || packageCode.isBlank()) {
                    log.debug("Skipping catalog row missing GE or package_code: {}", row);
                    skippedRows++;
                    continue;
                }

                String displayName = text(
                        row,
                        "generic_full_display_name",
                        "generic_name",
                        "display_name",
                        "name");
                if (displayName == null || displayName.isBlank()) {
                    displayName = geCode;
                }
                String packageName = text(row, "package_name", "pack_name");
                String strength = text(row, "strength_display_name", "strength", "strength_name");
                String formCode = text(row, "form_code", "dosage_form_code", "df_code");
                String formDescription = formCode != null
                        ? formNames.getOrDefault(formCode, text(row, "form_description", "form_name", "dosage_form"))
                        : null;
                String unitCode = text(row, "unit_code", "admin_unit_code", "uom_code", "dispensing_unit_code");
                String unitDescription = unitCode != null
                        ? unitNames.getOrDefault(
                                unitCode,
                                text(
                                        row,
                                        "admin_unit_description",
                                        "unit_description",
                                        "admin_unit_name",
                                        "uom_name"))
                        : null;

                JsonNode product = resolveProduct(geCode, packageCode, productByGeAndEtcd);
                String manufacturer = text(product, "manufacture_name", "manufacturer_name", "manufacturer");
                String brandName = text(product, "brand_name");
                if (brandName == null || brandName.isBlank()) {
                    brandName = text(row, "brand_name", "brand_full_display_name", "product_name");
                }
                String productStrength = text(product, "strength_display_name", "strength", "strength_name");
                if (productStrength != null && !productStrength.isBlank()) {
                    strength = productStrength;
                }
                String skuName = buildSkuName(brandName, displayName, packageName, packageCode, manufacturer);

                if (!active) {
                    odooWriter.archiveSku(packageCode);
                    archivedRows++;
                    continue;
                }

                activeGeCodes.add(geCode);
                activePackageCodes.add(packageCode);
                activePackageCountByGe.merge(geCode, 1, Integer::sum);

                String drugUuid = openmrsWriter.upsertGeDrug(
                        geCode, displayName, strength, formCode, formDescription, false);

                Integer uomId = null;
                if (unitCode != null && !unitCode.isBlank()) {
                    String unitUuid = HieUuid.forUnit(unitCode);
                    openmrsWriter.ensureUnitConcept(unitCode, unitDescription != null ? unitDescription : unitCode);
                    uomId = odooWriter.ensureUom(
                            unitUuid, unitCode, unitDescription != null ? unitDescription : unitCode);
                }

                odooWriter.upsertSku(
                        packageCode, skuName, drugUuid, geCode, uomId, true, manufacturer, strength);
            } catch (Exception e) {
                itemFailures.incrementAndGet();
                log.warn(
                        "Skipping catalog row after sync error (ge={}, package={}): {}",
                        text(row, "generic_concept_code", "ge_code", "GE", "generic_code"),
                        text(row, "package_code", "product_code", "ph_code", "code"),
                        e.toString());
                log.debug("Catalog row sync failure detail", e);
            }
        }

        int failures = itemFailures.get();
        log.info(
                "HIE sync complete: {} active GEs, {} active packages, {} archived, {} skipped incomplete, {} item failures",
                activeGeCodes.size(),
                activePackageCodes.size(),
                archivedRows,
                skippedRows,
                failures);
        if (failures > 0) {
            log.warn(
                    "HIE product catalogue sync finished with {} item failure(s); see warnings above",
                    failures);
        }
    }

    private Map<String, String> safePrefetchForms(AtomicInteger itemFailures) {
        try {
            return syncForms(itemFailures);
        } catch (Exception e) {
            itemFailures.incrementAndGet();
            log.warn(
                    "HIE /form prefetch failed; continuing with on-demand form upsert from catalog: {}",
                    e.toString());
            return Map.of();
        }
    }

    private Map<String, String> safePrefetchUnits(AtomicInteger itemFailures) {
        try {
            return syncUnits(itemFailures);
        } catch (Exception e) {
            itemFailures.incrementAndGet();
            log.warn(
                    "HIE /unit prefetch failed; continuing with on-demand unit upsert from catalog: {}",
                    e.toString());
            return Map.of();
        }
    }

    private void safePrefetchRoutes(AtomicInteger itemFailures) {
        try {
            syncRoutes(itemFailures);
        } catch (Exception e) {
            itemFailures.incrementAndGet();
            log.warn(
                    "HIE /route prefetch failed; continuing without full route seed: {}",
                    e.toString());
        }
    }

    private Map<String, String> syncForms(AtomicInteger itemFailures) throws Exception {
        Map<String, String> names = new HashMap<>();
        for (JsonNode row : terminologyClient.listAll("/form")) {
            String code = text(row, "form_code", "code");
            String desc = text(row, "form_description", "description", "name", "display");
            if (code == null || code.isBlank()) {
                continue;
            }
            names.put(code, desc != null ? desc : code);
            try {
                openmrsWriter.ensureFormConcept(code, names.get(code));
            } catch (Exception e) {
                itemFailures.incrementAndGet();
                log.warn("Skipping HIE form {} after OpenMRS error: {}", code, e.toString());
                log.debug("Form sync failure detail", e);
            }
        }
        log.info("Synced {} HIE forms (map size; see warnings for failures)", names.size());
        return names;
    }

    private Map<String, String> syncUnits(AtomicInteger itemFailures) throws Exception {
        Map<String, String> names = new HashMap<>();
        for (JsonNode row : terminologyClient.listAll("/unit")) {
            String code = text(row, "unit_code", "code");
            String desc = text(row, "unit_description", "description", "name", "display");
            if (code == null || code.isBlank()) {
                continue;
            }
            names.put(code, desc != null ? desc : code);
            try {
                String unitUuid = openmrsWriter.ensureUnitConcept(code, names.get(code));
                odooWriter.ensureUom(unitUuid, code, names.get(code));
            } catch (Exception e) {
                itemFailures.incrementAndGet();
                log.warn("Skipping HIE unit {} after sync error: {}", code, e.toString());
                log.debug("Unit sync failure detail", e);
            }
        }
        log.info("Synced {} HIE units (map size; see warnings for failures)", names.size());
        return names;
    }

    private void syncRoutes(AtomicInteger itemFailures) throws Exception {
        int count = 0;
        for (JsonNode row : terminologyClient.listAll("/route")) {
            String code = text(row, "route_code", "code");
            String desc = text(row, "route_description", "description", "name", "display");
            if (code == null || code.isBlank()) {
                continue;
            }
            try {
                openmrsWriter.ensureRouteConcept(code, desc != null ? desc : code);
                count++;
            } catch (Exception e) {
                itemFailures.incrementAndGet();
                log.warn("Skipping HIE route {} after OpenMRS error: {}", code, e.toString());
                log.debug("Route sync failure detail", e);
            }
        }
        log.info("Synced {} HIE routes", count);
    }

    private JsonNode resolveProduct(
            String geCode, String packageCode, Map<String, Optional<JsonNode>> cache) {
        String etcdId = HieTerminologyClient.etcdProductIdFromPackageCode(packageCode);
        if (etcdId == null || etcdId.isBlank()) {
            return null;
        }
        String cacheKey = geCode + "|" + etcdId;
        Optional<JsonNode> cached = cache.get(cacheKey);
        if (cached == null) {
            try {
                cached = Optional.ofNullable(terminologyClient.getProduct(geCode, etcdId));
            } catch (Exception e) {
                log.warn(
                        "HIE /product lookup failed for ge={} etcd={}: {}",
                        geCode,
                        etcdId,
                        e.toString());
                cached = Optional.empty();
            }
            cache.put(cacheKey, cached);
        }
        return cached.orElse(null);
    }

    /**
     * {@code brand (package) [package_code] — manufacturer}. Manufacturer suffix omitted when null/blank.
     */
    static String buildSkuName(
            String brand, String generic, String packageName, String packageCode, String manufacturer) {
        StringBuilder sb = new StringBuilder();
        if (brand != null && !brand.isBlank()) {
            sb.append(brand.trim());
        } else if (generic != null && !generic.isBlank()) {
            sb.append(generic.trim());
        }
        if (packageName != null && !packageName.isBlank()) {
            if (sb.length() > 0) {
                sb.append(' ');
            }
            sb.append('(').append(packageName.trim()).append(')');
        }
        if (packageCode != null && !packageCode.isBlank()) {
            if (sb.length() > 0) {
                sb.append(' ');
            }
            sb.append('[').append(packageCode.trim()).append(']');
        }
        if (manufacturer != null && !manufacturer.isBlank()) {
            if (sb.length() > 0) {
                sb.append(" — ");
            }
            sb.append(manufacturer.trim());
        }
        if (sb.length() == 0 && packageCode != null) {
            sb.append(packageCode);
        }
        return sb.toString();
    }

    private static String text(JsonNode node, String... fields) {
        if (node == null) {
            return null;
        }
        for (String field : fields) {
            if (node.has(field) && !node.get(field).isNull()) {
                String value = node.get(field).asText();
                if (value != null && !value.isBlank() && !"null".equalsIgnoreCase(value)) {
                    return value.trim();
                }
            }
            // case-insensitive fallback
            var fieldsIt = node.fieldNames();
            while (fieldsIt.hasNext()) {
                String key = fieldsIt.next();
                if (key.equalsIgnoreCase(field) && !node.get(key).isNull()) {
                    String value = node.get(key).asText();
                    if (value != null && !value.isBlank() && !"null".equalsIgnoreCase(value)) {
                        return value.trim();
                    }
                }
            }
        }
        return null;
    }
}
