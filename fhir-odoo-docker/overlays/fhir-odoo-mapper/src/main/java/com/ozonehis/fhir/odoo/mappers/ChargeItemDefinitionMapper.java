/*
 * Copyright © 2024, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.fhir.odoo.mappers;

import com.ozonehis.fhir.odoo.OdooConstants;
import com.ozonehis.fhir.odoo.model.BaseOdooModel;
import com.ozonehis.fhir.odoo.model.Currency;
import com.ozonehis.fhir.odoo.model.ExtId;
import com.ozonehis.fhir.odoo.model.OdooResource;
import com.ozonehis.fhir.odoo.model.Product;
import java.util.Map;
import org.apache.commons.collections4.MapUtils;
import org.hl7.fhir.r4.model.ChargeItemDefinition;
import org.hl7.fhir.r4.model.Enumerations;
import org.hl7.fhir.r4.model.Money;
import org.springframework.stereotype.Component;

@Component
public class ChargeItemDefinitionMapper<O extends BaseOdooModel & OdooResource>
        implements ToFhirMapping<O, ChargeItemDefinition> {

    @Override
    public ChargeItemDefinition toFhir(Map<String, O> resourceMap) {
        if (MapUtils.isEmpty(resourceMap)) {
            return null;
        }
        ChargeItemDefinition chargeItemDefinition = new ChargeItemDefinition();
        Product product = (Product) resourceMap.get(OdooConstants.MODEL_PRODUCT);
        ExtId extId = (ExtId) resourceMap.get(OdooConstants.MODEL_EXTERNAL_IDENTIFIER);
        Currency currency = (Currency) resourceMap.get(OdooConstants.MODEL_CURRENCY);

        if (product == null || extId == null) {
            return null;
        }
        chargeItemDefinition.setId(extId.getName());
        chargeItemDefinition.setName(product.getName());
        chargeItemDefinition.setDescription(product.getDescription());

        chargeItemDefinition.setDate(product.getLastUpdatedOn());

        // Possibly, this is wrong
        if (product.isActive()) {
            chargeItemDefinition.setStatus(Enumerations.PublicationStatus.ACTIVE);
        } else {
            chargeItemDefinition.setStatus(Enumerations.PublicationStatus.RETIRED);
        }

        // Price Component
        ChargeItemDefinition.ChargeItemDefinitionPropertyGroupPriceComponentComponent priceComponent =
                getPriceComponent(product, currency);
        chargeItemDefinition.addPropertyGroup().addPriceComponent(priceComponent);

        return chargeItemDefinition;
    }

    private static ChargeItemDefinition.ChargeItemDefinitionPropertyGroupPriceComponentComponent getPriceComponent(
            Product product, Currency currency) {
        ChargeItemDefinition.ChargeItemDefinitionPropertyGroupPriceComponentComponent priceComponent =
                new ChargeItemDefinition.ChargeItemDefinitionPropertyGroupPriceComponentComponent();
        Money money = new Money();
        // Sales price (Odoo list_price), not cost (standard_price).
        money.setValue(product.getListPrice());
        if (currency != null) {
            money.setCurrency(currency.getName());
            addCurrencyExtension(money, currency);
        }
        priceComponent.setAmount(money);
        // Base price
        priceComponent.setType(ChargeItemDefinition.ChargeItemDefinitionPriceComponentType.BASE);
        return priceComponent;
    }

    private static void addCurrencyExtension(Money money, Currency currency) {
        money.addExtension()
                .setUrl(OdooConstants.FHIR_OPENMRS_EXT_CURRENCY_SYMBOL)
                .setValue(new org.hl7.fhir.r4.model.StringType(currency.getSymbol()));
        money.addExtension()
                .setUrl(OdooConstants.FHIR_OPENMRS_EXT_CURRENCY_UNIT_LABEL)
                .setValue(new org.hl7.fhir.r4.model.StringType(currency.getCurrencyUnitLabel()));
        money.addExtension()
                .setUrl(OdooConstants.FHIR_OPENMRS_EXT_CURRENCY_SUBUNIT_LABEL)
                .setValue(new org.hl7.fhir.r4.model.StringType(currency.getCurrencySubunitLabel()));
    }
}
