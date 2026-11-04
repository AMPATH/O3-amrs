/*
 * Copyright © 2024, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.fhir.odoo.inventoryItem.impl;

import ca.uhn.fhir.rest.param.TokenAndListParam;
import com.ozonehis.fhir.odoo.OdooConstants;
import com.ozonehis.fhir.odoo.api.OpenmrsDrugProductResolver;
import com.ozonehis.fhir.odoo.api.StockQuantService;
import com.ozonehis.fhir.odoo.api.WarehouseService;
import com.ozonehis.fhir.odoo.inventoryItem.InventoryItemService;
import com.ozonehis.fhir.odoo.mappers.InventoryItemMapper;
import com.ozonehis.fhir.odoo.model.ExtId;
import com.ozonehis.fhir.odoo.model.OdooResource;
import com.ozonehis.fhir.odoo.model.Product;
import com.ozonehis.fhir.odoo.model.Warehouse;
import com.ozonehis.fhir.odoo.util.OdooValues;
import jakarta.annotation.Nonnull;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import lombok.extern.slf4j.Slf4j;
import org.hl7.fhir.r4.model.Bundle;
import org.openmrs.fhir.InventoryItem;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@SuppressWarnings("rawtypes, unchecked")
public class InventoryItemServiceImpl implements InventoryItemService {

    private final OpenmrsDrugProductResolver productResolver;

    private final WarehouseService warehouseService;

    private final StockQuantService stockQuantService;

    private final InventoryItemMapper inventoryItemMapper;

    @Autowired
    public InventoryItemServiceImpl(
            OpenmrsDrugProductResolver productResolver,
            WarehouseService warehouseService,
            StockQuantService stockQuantService,
            InventoryItemMapper inventoryItemMapper) {
        this.productResolver = productResolver;
        this.warehouseService = warehouseService;
        this.stockQuantService = stockQuantService;
        this.inventoryItemMapper = inventoryItemMapper;
    }

    @Override
    public Optional<InventoryItem> getById(@Nonnull String id) {
        List<Product> products = productResolver.resolveActive(id, true);
        if (products.isEmpty()) {
            log.warn("Inventory Item with ID {} not found as xml id or x_openmrs_drug_uuid", id);
            return Optional.empty();
        }
        return Optional.of(toInventoryItem(id, products, null, false));
    }

    @Override
    public Bundle searchForInventoryItems(TokenAndListParam code, TokenAndListParam location) {
        Bundle bundle = new Bundle();
        List<String> codes = OdooValues.tokenValues(code);
        if (codes.isEmpty()) {
            return bundle;
        }
        List<String> locationUuids = OdooValues.tokenValues(location);
        Warehouse warehouse = resolveWarehouse(locationUuids);
        boolean locationRequested = !locationUuids.isEmpty();
        for (String drugCode : codes) {
            List<Product> products = productResolver.resolveActive(drugCode, true);
            if (products.isEmpty()) {
                continue;
            }
            bundle.addEntry().setResource(toInventoryItem(drugCode, products, warehouse, locationRequested));
        }
        return bundle;
    }

    private Warehouse resolveWarehouse(List<String> locationUuids) {
        for (String locationUuid : locationUuids) {
            Optional<Warehouse> found = warehouseService.findByOpenmrsLocationUuid(locationUuid);
            if (found.isPresent() && found.get().getLotStockId() != null) {
                return found.get();
            }
        }
        if (!locationUuids.isEmpty()) {
            log.warn(
                    "No warehouse for OpenMRS location(s) {}; InventoryItem qty will be 0 for this search",
                    locationUuids);
        }
        return null;
    }

    private InventoryItem toInventoryItem(
            String drugCode, List<Product> products, Warehouse warehouse, boolean locationRequested) {
        Product primary = products.get(0);
        Product aggregated = copyProduct(primary);
        aggregated.setQuantityAvailable(quantityFor(products, warehouse, locationRequested));
        ExtId extId = productResolver.syntheticExtId(drugCode, primary.getId());
        Map<String, OdooResource> resourceMap = Map.of(
                OdooConstants.MODEL_PRODUCT, aggregated,
                OdooConstants.MODEL_EXTERNAL_IDENTIFIER, extId);
        return inventoryItemMapper.toFhir(resourceMap);
    }

    private double quantityFor(List<Product> products, Warehouse warehouse, boolean locationRequested) {
        if (warehouse != null && warehouse.getLotStockId() != null) {
            return stockQuantService.freeQty(products, warehouse.getLotStockId());
        }
        if (locationRequested || warehouse != null) {
            return 0d;
        }
        double total = 0d;
        for (Product product : products) {
            total += product.getQuantityAvailable() != null ? product.getQuantityAvailable() : 0d;
        }
        return total;
    }

    private static Product copyProduct(Product source) {
        Product copy = new Product();
        copy.setId(source.getId());
        copy.setName(source.getName());
        copy.setDisplayName(source.getDisplayName());
        copy.setDescription(source.getDescription());
        copy.setUomName(source.getUomName());
        copy.setQuantityAvailable(source.getQuantityAvailable());
        copy.setListPrice(source.getListPrice());
        copy.setPublicPrice(source.getPublicPrice());
        copy.setStandardPrice(source.getStandardPrice());
        copy.setActive(source.isActive());
        copy.setCode(source.getCode());
        copy.setCurrencyId(source.getCurrencyId());
        copy.setType(source.getType());
        copy.setConceptSource(source.getConceptSource());
        copy.setConceptCode(source.getConceptCode());
        copy.setDrugStrength(source.getDrugStrength());
        copy.setOpenmrsDrugUuid(source.getOpenmrsDrugUuid());
        return copy;
    }
}
