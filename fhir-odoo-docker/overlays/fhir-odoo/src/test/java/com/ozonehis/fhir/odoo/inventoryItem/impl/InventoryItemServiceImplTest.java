/*
 * Copyright © 2024, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.fhir.odoo.inventoryItem.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import ca.uhn.fhir.rest.param.TokenAndListParam;
import ca.uhn.fhir.rest.param.TokenOrListParam;
import ca.uhn.fhir.rest.param.TokenParam;
import com.ozonehis.fhir.odoo.OdooConstants;
import com.ozonehis.fhir.odoo.api.OpenmrsDrugProductResolver;
import com.ozonehis.fhir.odoo.api.StockQuantService;
import com.ozonehis.fhir.odoo.api.WarehouseService;
import com.ozonehis.fhir.odoo.mappers.InventoryItemMapper;
import com.ozonehis.fhir.odoo.model.ExtId;
import com.ozonehis.fhir.odoo.model.OdooResource;
import com.ozonehis.fhir.odoo.model.Product;
import com.ozonehis.fhir.odoo.model.Warehouse;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.openmrs.fhir.InventoryItem;

@ExtendWith(MockitoExtension.class)
@SuppressWarnings({ "rawtypes", "unchecked" })
class InventoryItemServiceImplTest {

    @Mock
    private OpenmrsDrugProductResolver productResolver;

    @Mock
    private WarehouseService warehouseService;

    @Mock
    private StockQuantService stockQuantService;

    @Mock
    private InventoryItemMapper inventoryItemMapper;

    private InventoryItemServiceImpl service;

    @BeforeEach
    void setUp() {
        service = new InventoryItemServiceImpl(
                productResolver, warehouseService, stockQuantService, inventoryItemMapper);
        when(productResolver.syntheticExtId(any(), anyInt())).thenReturn(new ExtId());
        when(inventoryItemMapper.toFhir(any())).thenReturn(new InventoryItem());
    }

    @Test
    void search_unknownLocation_doesNotUseGlobalQty() {
        Product product = productWithGlobalQty(99d);
        when(productResolver.resolveActive("drug-uuid", true)).thenReturn(List.of(product));
        when(warehouseService.findByOpenmrsLocationUuid("unknown-loc")).thenReturn(Optional.empty());

        service.searchForInventoryItems(code("drug-uuid"), location("unknown-loc"));

        assertEquals(0d, capturedQuantity());
    }

    @Test
    void search_triesAncestorLocationTokensUntilWarehouseFound() {
        Product product = productWithGlobalQty(99d);
        Warehouse warehouse = new Warehouse();
        warehouse.setLotStockId(42);
        when(productResolver.resolveActive("drug-uuid", true)).thenReturn(List.of(product));
        when(warehouseService.findByOpenmrsLocationUuid("child-uuid")).thenReturn(Optional.empty());
        when(warehouseService.findByOpenmrsLocationUuid("facility-uuid")).thenReturn(Optional.of(warehouse));
        when(stockQuantService.freeQty(any(), eq(42))).thenReturn(7d);

        TokenAndListParam location = new TokenAndListParam();
        TokenOrListParam or = new TokenOrListParam();
        or.add(new TokenParam("child-uuid"));
        or.add(new TokenParam("facility-uuid"));
        location.addAnd(or);

        service.searchForInventoryItems(code("drug-uuid"), location);

        assertEquals(7d, capturedQuantity());
        verify(stockQuantService).freeQty(any(), eq(42));
    }

    @Test
    void search_withoutLocation_usesGlobalQty() {
        Product product = productWithGlobalQty(99d);
        when(productResolver.resolveActive("drug-uuid", true)).thenReturn(List.of(product));

        service.searchForInventoryItems(code("drug-uuid"), null);

        assertEquals(99d, capturedQuantity());
    }

    private Product productWithGlobalQty(double qty) {
        Product product = new Product();
        product.setId(1);
        product.setQuantityAvailable(qty);
        return product;
    }

    private TokenAndListParam code(String value) {
        TokenAndListParam param = new TokenAndListParam();
        param.addAnd(new TokenOrListParam().add(new TokenParam(value)));
        return param;
    }

    private TokenAndListParam location(String value) {
        return code(value);
    }

    private double capturedQuantity() {
        ArgumentCaptor<Map<String, OdooResource>> captor = ArgumentCaptor.forClass(Map.class);
        verify(inventoryItemMapper).toFhir(captor.capture());
        Product aggregated = (Product) captor.getValue().get(OdooConstants.MODEL_PRODUCT);
        return aggregated.getQuantityAvailable();
    }
}
