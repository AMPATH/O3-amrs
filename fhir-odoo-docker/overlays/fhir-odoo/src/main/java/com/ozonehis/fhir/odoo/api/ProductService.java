/*
 * Copyright © 2024, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.fhir.odoo.api;

import static com.ozonehis.fhir.odoo.OdooConstants.LOINC_SOURCE;
import static com.ozonehis.fhir.odoo.OdooConstants.MODEL_PRODUCT;
import static com.ozonehis.fhir.odoo.util.OdooUtils.get;

import com.odoojava.api.FilterCollection;
import com.odoojava.api.OdooApiException;
import com.odoojava.api.Row;
import com.ozonehis.fhir.odoo.OdooConstants;
import com.ozonehis.fhir.odoo.model.Product;
import com.ozonehis.fhir.odoo.util.OdooValues;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Date;
import java.util.List;
import java.util.Optional;
import org.springframework.stereotype.Service;

@Service
public class ProductService extends BaseOdooService<Product> implements OdooService<Product> {

    @Override
    protected String modelName() {
        return OdooConstants.MODEL_PRODUCT;
    }

    @Override
    protected String[] modelFields() {
        return new Product().fields();
    }

    @Override
    protected Product mapRowToResource(Row row) {
        Product product = new Product();
        product.setId(get(row, "id"));
        product.setDisplayName((String) row.get("display_name"));
        product.setName((String) row.get("name"));
        product.setUomName((String) row.get("uom_name"));
        product.setQuantityAvailable(OdooValues.asDouble(row.get("qty_available")));
        product.setListPrice(OdooValues.asDouble(row.get("list_price")));
        product.setPublicPrice(OdooValues.asDouble(row.get("lst_price")));
        product.setStandardPrice(OdooValues.asDouble(row.get("standard_price")));
        product.setConceptSource((String) row.get("x_concept_source"));
        product.setConceptCode((String) row.get("x_concept_code"));
        product.setDrugStrength((String) row.get("x_drug_strength"));
        product.setOpenmrsDrugUuid((String) row.get("x_openmrs_drug_uuid"));

        var type = row.get("type");
        if (type != null) {
            product.setType((String) row.get("type"));
        }

        var active = row.get("active");
        if (active != null) {
            product.setActive((boolean) row.get("active"));
        }
        product.setCode((String) row.get("code"));

        Integer currencyId = OdooValues.asInteger(row.get("currency_id"));
        if (currencyId != null) {
            product.setCurrencyId(currencyId);
        }
        // Audit fields
        var createdOn = get(row, "create_date");
        if (createdOn != null) {
            product.setCreatedOn((Date) createdOn);
        }
        var createdBy = get(row, "create_uid");
        if (createdBy != null) {
            product.setCreatedBy((Integer) createdBy);
        }

        var lastUpdatedOn = get(row, "write_date");
        if (lastUpdatedOn != null) {
            product.setLastUpdatedOn((Date) lastUpdatedOn);
        }

        var lastUpdatedBy = get(row, "write_uid");
        if (lastUpdatedBy != null) {
            product.setLastUpdatedBy((Integer) lastUpdatedBy);
        }

        return product;
    }

    public Optional<Product> getByConceptCode(String conceptCode) {
        FilterCollection filters = new FilterCollection();
        try {
            filters.add("x_concept_code", "=", conceptCode);
            filters.add("x_concept_source", "=", LOINC_SOURCE);
            Collection<Product> results = this.search(filters);
            if (results.size() > 1) {
                throw new RuntimeException(
                        "Multiple Products found for " + MODEL_PRODUCT + " with concept code " + conceptCode);
            } else if (results.size() == 1) {
                return results.stream().findFirst();
            }

            return Optional.empty();
        } catch (OdooApiException e) {
            throw new RuntimeException(e);
        }
    }

    /**
     * All active products that share an OpenMRS drug UUID (HIE multi-SKU).
     */
    public List<Product> searchByOpenmrsDrugUuid(String openmrsDrugUuid) {
        if (openmrsDrugUuid == null || openmrsDrugUuid.isBlank()) {
            return List.of();
        }
        try {
            FilterCollection filters = new FilterCollection();
            filters.add("x_openmrs_drug_uuid", "=", openmrsDrugUuid);
            filters.add("active", "=", true);
            return new ArrayList<>(this.search(filters));
        } catch (OdooApiException e) {
            throw new RuntimeException("Error searching products by x_openmrs_drug_uuid " + openmrsDrugUuid, e);
        }
    }
}
