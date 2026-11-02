/*
 * Copyright © 2024, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.fhir.odoo.inventoryItem;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.when;
import static org.mockito.MockitoAnnotations.openMocks;

import ca.uhn.fhir.rest.param.TokenAndListParam;
import ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException;
import java.util.Optional;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.IdType;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.openmrs.fhir.InventoryItem;

class InventoryItemResourceProviderTest {

    @Mock
    private InventoryItemService inventoryItemService;

    @InjectMocks
    private InventoryItemResourceProvider inventoryItemResourceProvider;

    private static AutoCloseable mockCloser;

    @BeforeEach
    void setUp() {
        mockCloser = openMocks(this);
    }

    @AfterAll
    public static void tearDown() throws Exception {
        mockCloser.close();
    }

    @Test
    void read_shouldReturnInventoryItemWhenIdExists() {
        IdType id = new IdType("1");
        InventoryItem expectedItem = new InventoryItem();
        when(inventoryItemService.getById("1")).thenReturn(Optional.of(expectedItem));

        InventoryItem result = inventoryItemResourceProvider.read(id);

        assertEquals(expectedItem, result);
    }

    @Test
    void read_shouldThrowResourceNotFoundExceptionWhenIdDoesNotExist() {
        IdType id = new IdType("1");
        when(inventoryItemService.getById("1")).thenReturn(Optional.empty());

        assertThrows(ResourceNotFoundException.class, () -> inventoryItemResourceProvider.read(id));
    }

    @Test
    void search_shouldReturnBundleWhenCorrectParamsIsProvided() {
        TokenAndListParam code = new TokenAndListParam();
        Bundle expectedBundle = new Bundle();
        when(inventoryItemService.searchForInventoryItems(code, null)).thenReturn(expectedBundle);

        Bundle result = inventoryItemResourceProvider.searchForInventoryItems(code, null);

        assertEquals(expectedBundle, result);
    }

    @Test
    void search_shouldForwardLocationParam() {
        TokenAndListParam code = new TokenAndListParam();
        TokenAndListParam location = new TokenAndListParam();
        Bundle expectedBundle = new Bundle();
        when(inventoryItemService.searchForInventoryItems(code, location)).thenReturn(expectedBundle);

        Bundle result = inventoryItemResourceProvider.searchForInventoryItems(code, location);

        assertEquals(expectedBundle, result);
    }
}
