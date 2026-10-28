/*
 * Copyright © 2024, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.fhir.odoo.inventoryItem;

import ca.uhn.fhir.rest.annotation.IdParam;
import ca.uhn.fhir.rest.annotation.OptionalParam;
import ca.uhn.fhir.rest.annotation.Read;
import ca.uhn.fhir.rest.annotation.Search;
import ca.uhn.fhir.rest.param.TokenAndListParam;
import ca.uhn.fhir.rest.server.IResourceProvider;
import ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException;
import com.ozonehis.fhir.annotations.FhirOdooProvider;
import org.hl7.fhir.instance.model.api.IBaseResource;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.IdType;
import org.openmrs.fhir.InventoryItem;
import org.springframework.beans.factory.annotation.Autowired;

@FhirOdooProvider
@SuppressWarnings("unused")
public class InventoryItemResourceProvider implements IResourceProvider {

    private final InventoryItemService inventoryItemService;

    @Autowired
    public InventoryItemResourceProvider(InventoryItemService inventoryItemService) {
        this.inventoryItemService = inventoryItemService;
    }

    @Override
    public Class<? extends IBaseResource> getResourceType() {
        return InventoryItem.class;
    }

    @Read
    public InventoryItem read(@IdParam IdType id) {
        return inventoryItemService
                .getById(id.getIdPart())
                .orElseThrow(
                        () -> new ResourceNotFoundException("InventoryItem with id " + id.getIdPart() + " not found"));
    }

    @Search
    public Bundle searchForInventoryItems(
            @OptionalParam(name = InventoryItem.SP_CODE) TokenAndListParam code,
            @OptionalParam(name = "location") TokenAndListParam location) {
        return inventoryItemService.searchForInventoryItems(code, location);
    }
}
