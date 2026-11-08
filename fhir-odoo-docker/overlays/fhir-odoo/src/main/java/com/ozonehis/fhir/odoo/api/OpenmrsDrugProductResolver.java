/*
 * Copyright © 2024, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.fhir.odoo.api;

import com.ozonehis.fhir.odoo.OdooConstants;
import com.ozonehis.fhir.odoo.model.ExtId;
import com.ozonehis.fhir.odoo.model.Product;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * Resolves Odoo products for an OpenMRS drug UUID.
 *
 * <p>CSV-era products use {@code ir.model.data} name = UUID. HIE SKUs store the UUID on
 * {@code x_openmrs_drug_uuid} and use the package code as the XML id.
 */
@Component
public class OpenmrsDrugProductResolver {

    private final ExtIdService extIdService;

    private final ProductService productService;

    @Autowired
    public OpenmrsDrugProductResolver(ExtIdService extIdService, ProductService productService) {
        this.extIdService = extIdService;
        this.productService = productService;
    }

    public List<Product> resolveActive(String code, boolean storableOnly) {
        List<Product> fromXmlId = new ArrayList<>();
        Collection<ExtId> extIds = extIdService.getResIdsByNameAndModel(List.of(code), OdooConstants.MODEL_PRODUCT);
        for (ExtId extId : extIds) {
            Optional<Product> product = productService.getById(String.valueOf(extId.getResId()));
            if (product.isPresent() && isEligible(product.get(), storableOnly)) {
                fromXmlId.add(product.get());
            }
        }
        if (!fromXmlId.isEmpty()) {
            return fromXmlId;
        }
        return productService.searchByOpenmrsDrugUuid(code).stream()
                .filter(product -> isEligible(product, storableOnly))
                .toList();
    }

    public ExtId syntheticExtId(String code, int resId) {
        ExtId extId = new ExtId();
        extId.setName(code);
        extId.setModel(OdooConstants.MODEL_PRODUCT);
        extId.setModule(OdooConstants.INIT_MODULE);
        extId.setResId(resId);
        return extId;
    }

    private static boolean isEligible(Product product, boolean storableOnly) {
        if (product == null || !product.isActive()) {
            return false;
        }
        if (!storableOnly) {
            return true;
        }
        return OdooConstants.PRODUCT_TYPE_STORABLE.equals(product.getType());
    }
}
