/*
 * Copyright © 2024, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.fhir.odoo.api;

import static com.ozonehis.fhir.odoo.util.OdooValues.asInteger;

import com.odoojava.api.FilterCollection;
import com.odoojava.api.OdooApiException;
import com.odoojava.api.Row;
import com.ozonehis.fhir.odoo.OdooConstants;
import com.ozonehis.fhir.odoo.model.ExtId;
import com.ozonehis.fhir.odoo.model.Warehouse;
import java.util.Collection;
import java.util.Optional;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Slf4j
@Service
public class WarehouseService extends BaseOdooService<Warehouse> implements OdooService<Warehouse> {

    private final ExtIdService extIdService;

    @Autowired
    public WarehouseService(ExtIdService extIdService) {
        this.extIdService = extIdService;
    }

    @Override
    protected String modelName() {
        return OdooConstants.MODEL_WAREHOUSE;
    }

    @Override
    protected String[] modelFields() {
        return new Warehouse().fields();
    }

    @Override
    protected Warehouse mapRowToResource(Row row) {
        Warehouse warehouse = new Warehouse();
        Integer id = asInteger(row.get("id"));
        if (id != null) {
            warehouse.setId(id);
        }
        warehouse.setName((String) row.get("name"));
        warehouse.setDisplayName((String) row.get("display_name"));
        warehouse.setCompanyId(asInteger(row.get("company_id")));
        warehouse.setLotStockId(asInteger(row.get("lot_stock_id")));
        return warehouse;
    }

    /**
     * Maps an OpenMRS location UUID to the first warehouse of the matching Odoo company
     * ({@code ir.model.data} {@code init.<uuid>} on {@code res.company}).
     */
    public Optional<Warehouse> findByOpenmrsLocationUuid(String locationUuid) {
        if (locationUuid == null || locationUuid.isBlank()) {
            return Optional.empty();
        }
        Optional<ExtId> companyExt = extIdService.getByNameAndModel(locationUuid, OdooConstants.MODEL_COMPANY);
        if (companyExt.isEmpty()) {
            log.warn("No Odoo company xml id for OpenMRS location {}", locationUuid);
            return Optional.empty();
        }
        try {
            FilterCollection filters = new FilterCollection();
            filters.add("company_id", "=", companyExt.get().getResId());
            Collection<Warehouse> warehouses = search(filters);
            return warehouses.stream().findFirst();
        } catch (OdooApiException e) {
            throw new RuntimeException("Error resolving warehouse for location " + locationUuid, e);
        }
    }
}
