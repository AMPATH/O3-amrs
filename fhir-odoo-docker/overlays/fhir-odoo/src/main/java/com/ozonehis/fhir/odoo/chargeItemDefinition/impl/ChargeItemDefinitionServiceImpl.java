/*
 * Copyright © 2024, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.fhir.odoo.chargeItemDefinition.impl;

import ca.uhn.fhir.rest.param.TokenAndListParam;
import com.ozonehis.fhir.odoo.OdooConstants;
import com.ozonehis.fhir.odoo.api.CurrencyService;
import com.ozonehis.fhir.odoo.api.OpenmrsDrugProductResolver;
import com.ozonehis.fhir.odoo.chargeItemDefinition.ChargeItemDefinitionService;
import com.ozonehis.fhir.odoo.mappers.ChargeItemDefinitionMapper;
import com.ozonehis.fhir.odoo.model.Currency;
import com.ozonehis.fhir.odoo.model.ExtId;
import com.ozonehis.fhir.odoo.model.OdooResource;
import com.ozonehis.fhir.odoo.model.Product;
import com.ozonehis.fhir.odoo.util.OdooValues;
import jakarta.annotation.Nonnull;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import lombok.extern.slf4j.Slf4j;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.ChargeItemDefinition;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@SuppressWarnings("rawtypes, unchecked")
public class ChargeItemDefinitionServiceImpl implements ChargeItemDefinitionService {

    private final OpenmrsDrugProductResolver productResolver;

    private final CurrencyService currencyService;

    private final ChargeItemDefinitionMapper chargeItemDefinitionMapper;

    @Autowired
    public ChargeItemDefinitionServiceImpl(
            OpenmrsDrugProductResolver productResolver,
            CurrencyService currencyService,
            ChargeItemDefinitionMapper chargeItemDefinitionMapper) {
        this.productResolver = productResolver;
        this.currencyService = currencyService;
        this.chargeItemDefinitionMapper = chargeItemDefinitionMapper;
    }

    @Override
    public Bundle searchForChargeItemDefinitions(TokenAndListParam code) {
        Bundle bundle = new Bundle();
        List<String> codes = OdooValues.tokenValues(code);
        for (String drugCode : codes) {
            toChargeItemDefinition(drugCode).ifPresent(resource -> bundle.addEntry().setResource(resource));
        }
        return bundle;
    }

    @Override
    public Optional<ChargeItemDefinition> getById(@Nonnull String id) {
        return toChargeItemDefinition(id);
    }

    private Optional<ChargeItemDefinition> toChargeItemDefinition(String drugCode) {
        List<Product> products = productResolver.resolveActive(drugCode, false);
        if (products.isEmpty()) {
            log.warn("ChargeItemDefinition {} not found as xml id or x_openmrs_drug_uuid", drugCode);
            return Optional.empty();
        }
        Product priced = pickPricedProduct(products);
        ExtId extId = productResolver.syntheticExtId(drugCode, priced.getId());
        Map<String, OdooResource> resourceMap = new HashMap<>();
        resourceMap.put(OdooConstants.MODEL_PRODUCT, priced);
        resourceMap.put(OdooConstants.MODEL_EXTERNAL_IDENTIFIER, extId);
        if (priced.getCurrencyId() != null) {
            Optional<Currency> currency = currencyService.getById(String.valueOf(priced.getCurrencyId()));
            currency.ifPresent(value -> resourceMap.put(OdooConstants.MODEL_CURRENCY, value));
        }
        return Optional.of(chargeItemDefinitionMapper.toFhir(resourceMap));
    }

    private static Product pickPricedProduct(List<Product> products) {
        return products.stream()
                .filter(p -> p.getListPrice() != null && p.getListPrice() > 0)
                .findFirst()
                .orElse(products.get(0));
    }
}
