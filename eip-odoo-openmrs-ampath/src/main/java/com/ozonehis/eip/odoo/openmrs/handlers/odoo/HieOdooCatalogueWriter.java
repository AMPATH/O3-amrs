/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.handlers.odoo;

import static java.util.Arrays.asList;

import com.ozonehis.eip.odoo.openmrs.Constants;
import com.ozonehis.eip.odoo.openmrs.client.OdooClient;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.openmrs.eip.EIPException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Upserts Odoo UOM (shared UUID5 with OpenMRS unit) and drug SKU products linked by x_openmrs_drug_uuid.
 */
@Slf4j
@Component
public class HieOdooCatalogueWriter {

    private static final String INIT_MODULE = "init";

    @Autowired
    private OdooClient odooClient;

    @Value("${hie.odoo.drug.category.external.id:categ_products_drug_orders}")
    private String drugCategoryExternalId;

    /**
     * Ensures an Odoo UoM whose external id is the shared unit UUID5.
     *
     * @param unitUuid UUID5({@code hie:unit:{code}}) — also {@code ir.model.data} name
     * @param unitCode HIE unit code (e.g. {@code UM415})
     * @param unitName human label (e.g. {@code tablet})
     */
    public Integer ensureUom(String unitUuid, String unitCode, String unitName) {
        String displayName = buildUomDisplayName(unitCode, unitName);
        Integer existing = findResId(Constants.UOM_MODEL, unitUuid);
        if (existing != null) {
            // Refresh display name (older syncs used "UM415 [uuid-prefix]").
            try {
                odooClient.write(Constants.UOM_MODEL, List.of(List.of(existing), Map.of("name", displayName)));
            } catch (RuntimeException e) {
                log.debug("Could not refresh UOM {} name to {}: {}", existing, displayName, e.getMessage());
            }
            return existing;
        }

        Integer categoryId = resolveHieUomCategoryId();
        Map<String, Object> vals = new HashMap<>();
        vals.put("name", displayName);
        vals.put("category_id", categoryId);
        vals.put("rounding", 0.01);
        if (categoryHasReferenceUom(categoryId)) {
            vals.put("uom_type", "bigger");
            vals.put("factor", 1.0);
        } else {
            vals.put("uom_type", "reference");
        }

        Integer uomId;
        try {
            uomId = odooClient.create(Constants.UOM_MODEL, List.of(vals));
        } catch (RuntimeException e) {
            // Rare: name clash in category — disambiguate with unit code.
            String fallback = displayName;
            if (unitCode != null && !unitCode.isBlank() && !displayName.contains(unitCode)) {
                fallback = displayName + " (" + unitCode + ")";
                vals.put("name", fallback);
                uomId = odooClient.create(Constants.UOM_MODEL, List.of(vals));
            } else {
                throw e;
            }
            displayName = fallback;
        }
        createExternalId(Constants.UOM_MODEL, unitUuid, uomId);
        log.info("Created Odoo UOM {} id={} external={}", displayName, uomId, unitUuid);
        return uomId;
    }

    /** Prefer human description; fall back to HIE unit code. Never use UUID in the label. */
    static String buildUomDisplayName(String unitCode, String unitName) {
        String desc = unitName != null ? unitName.trim() : "";
        if (!desc.isBlank() && (unitCode == null || !desc.equalsIgnoreCase(unitCode.trim()))) {
            return desc;
        }
        if (unitCode != null && !unitCode.isBlank()) {
            return unitCode.trim();
        }
        return "HIE unit";
    }

    /** @deprecated use {@link #ensureUom(String, String, String)} */
    public Integer ensureUom(String unitUuid, String unitName) {
        return ensureUom(unitUuid, null, unitName);
    }

    private boolean categoryHasReferenceUom(Integer categoryId) {
        Object[] records = odooClient.searchAndRead(
                Constants.UOM_MODEL,
                asList(asList("category_id", "=", categoryId), asList("uom_type", "=", "reference")),
                asList("id"));
        return records != null && records.length > 0;
    }

    private Integer resolveHieUomCategoryId() {
        final String categoryName = "HIE Product Catalogue";
        Object[] cats = odooClient.searchAndRead(
                "uom.category", asList(asList("name", "=", categoryName)), asList("id", "name"));
        if (cats != null && cats.length > 0) {
            Object id = ((Map<?, ?>) cats[0]).get("id");
            if (id instanceof Number n) {
                return n.intValue();
            }
        }
        Integer created = odooClient.create("uom.category", List.of(Map.of("name", categoryName)));
        log.info("Created Odoo uom.category '{}' id={}", categoryName, created);
        return created;
    }

    public Integer upsertSku(
            String packageCode,
            String displayName,
            String openmrsDrugUuid,
            String geCode,
            Integer uomId,
            boolean active) {
        return upsertSku(packageCode, displayName, openmrsDrugUuid, geCode, uomId, active, null, null);
    }

    public Integer upsertSku(
            String packageCode,
            String displayName,
            String openmrsDrugUuid,
            String geCode,
            Integer uomId,
            boolean active,
            String manufacturer,
            String strength) {
        Integer existing = findExistingSkuId(packageCode);
        Map<String, Object> vals = new HashMap<>();
        vals.put("name", displayName);
        vals.put("default_code", packageCode);
        vals.put("type", "product");
        vals.put("tracking", "lot");
        vals.put("use_expiration_date", true);
        vals.put("sale_ok", true);
        vals.put("purchase_ok", true);
        vals.put("active", active);
        if (uomId != null) {
            vals.put("uom_id", uomId);
            vals.put("uom_po_id", uomId);
        }
        Integer categId = findResId("product.category", drugCategoryExternalId);
        if (categId != null) {
            vals.put("categ_id", categId);
        }
        vals.put("x_openmrs_drug_uuid", openmrsDrugUuid);
        if (geCode != null) {
            vals.put("x_concept_code", geCode);
        }
        if (manufacturer != null && !manufacturer.isBlank()) {
            vals.put("x_hie_manufacturer", manufacturer.trim());
        } else {
            vals.put("x_hie_manufacturer", false); // clear in Odoo
        }
        if (strength != null && !strength.isBlank()) {
            vals.put("x_drug_strength", strength.trim());
        }

        if (existing == null) {
            Integer productId = odooClient.create(Constants.PRODUCT_MODEL, List.of(vals));
            createExternalId(Constants.PRODUCT_MODEL, packageCode, productId);
            log.info("Created Odoo SKU {} id={} drugUuid={}", packageCode, productId, openmrsDrugUuid);
            return productId;
        }

        odooClient.write(Constants.PRODUCT_MODEL, List.of(List.of(existing), vals));
        log.debug("Updated Odoo SKU {} id={}", packageCode, existing);
        return existing;
    }

    public void archiveSku(String packageCode) {
        Integer existing = findExistingSkuId(packageCode);
        if (existing == null) {
            return;
        }
        odooClient.write(Constants.PRODUCT_MODEL, List.of(List.of(existing), Map.of("active", false)));
        log.info("Archived Odoo SKU {}", packageCode);
    }

    /**
     * Prefer unique {@code default_code} (= package code). External ids are not authoritative.
     */
    private Integer findExistingSkuId(String packageCode) {
        if (packageCode == null || packageCode.isBlank()) {
            return null;
        }
        Object[] byCode = odooClient.searchAndRead(
                Constants.PRODUCT_MODEL,
                asList(asList("default_code", "=", packageCode.trim())),
                asList("id", "default_code", "active"));
        if (byCode != null && byCode.length > 0) {
            if (byCode.length > 1) {
                log.warn(
                        "Multiple Odoo products with default_code={}; updating id={}",
                        packageCode,
                        ((Map<?, ?>) byCode[0]).get("id"));
            }
            Object id = ((Map<?, ?>) byCode[0]).get("id");
            return id instanceof Number n ? n.intValue() : null;
        }
        return findResId(Constants.PRODUCT_MODEL, packageCode);
    }

    private Integer findResId(String model, String externalName) {
        Object[] records = odooClient.searchAndRead(
                Constants.IR_MODEL,
                asList(asList("model", "=", model), asList("name", "=", externalName), asList("module", "=", INIT_MODULE)),
                asList("res_id", "name", "model"));
        if (records == null || records.length == 0) {
            // Also try without module filter (some environments omit module)
            records = odooClient.searchAndRead(
                    Constants.IR_MODEL,
                    asList(asList("model", "=", model), asList("name", "=", externalName)),
                    asList("res_id", "name", "model"));
        }
        if (records == null || records.length == 0) {
            return null;
        }
        Object resId = ((Map<?, ?>) records[0]).get("res_id");
        return resId instanceof Number n ? n.intValue() : null;
    }

    private void createExternalId(String model, String name, Integer resId) {
        Map<String, Object> vals = new HashMap<>();
        vals.put("module", INIT_MODULE);
        vals.put("name", name);
        vals.put("model", model);
        vals.put("res_id", resId);
        try {
            odooClient.create(Constants.IR_MODEL, List.of(vals));
        } catch (RuntimeException e) {
            // Idempotent: already exists
            log.debug("ir.model.data create for {}.{} may already exist: {}", model, name, e.getMessage());
        }
    }

    private Integer resolveUomCategoryId() {
        Object[] cats = odooClient.searchAndRead(
                "uom.category", asList(asList("name", "=", "Unit")), asList("id", "name"));
        if (cats != null && cats.length > 0) {
            Object id = ((Map<?, ?>) cats[0]).get("id");
            if (id instanceof Number n) {
                return n.intValue();
            }
        }
        // Fallback: first category
        Object[] any = odooClient.searchAndRead("uom.category", List.of(), asList("id", "name"));
        if (any == null || any.length == 0) {
            throw new EIPException("No uom.category found in Odoo");
        }
        Object id = ((Map<?, ?>) any[0]).get("id");
        return id instanceof Number n ? n.intValue() : null;
    }
}
