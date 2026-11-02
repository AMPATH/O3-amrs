/*
 * Copyright © 2024, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.fhir.odoo;

import lombok.NoArgsConstructor;

@NoArgsConstructor
public class OdooConstants {

    public static final String FHIR_OPENMRS_SYSTEM_PREFIX = "http://fhir.openmrs.org/";

    public static final String FHIR_OPENMRS_EXT_PREFIX = FHIR_OPENMRS_SYSTEM_PREFIX + "ext/";

    public static final String FHIR_OPENMRS_EXT_CURRENCY = FHIR_OPENMRS_EXT_PREFIX + "currency/";

    public static final String FHIR_OPENMRS_EXT_CURRENCY_SYMBOL = FHIR_OPENMRS_EXT_CURRENCY + "symbol";

    public static final String FHIR_OPENMRS_EXT_CURRENCY_UNIT_LABEL = FHIR_OPENMRS_EXT_CURRENCY + "unit-label";

    public static final String FHIR_OPENMRS_EXT_CURRENCY_SUBUNIT_LABEL = FHIR_OPENMRS_EXT_CURRENCY + "subunit-label";

    public static final String FHIR_OPENMRS_CONCEPT_SYSTEM_PREFIX = FHIR_OPENMRS_SYSTEM_PREFIX + "concept-system/";

    public static final String FHIR_OPENMRS_INVENTORY_ITEM = FHIR_OPENMRS_CONCEPT_SYSTEM_PREFIX + "inventory-item";

    public static final String FHIR_OPENMRS_FHIR_EXT_MEDICINE = FHIR_OPENMRS_EXT_PREFIX + "medicine";

    public static final String FHIR_OPENMRS_EXT_DRUG_NAME = FHIR_OPENMRS_FHIR_EXT_MEDICINE + "#drugName";

    public static final String FHIR_OPENMRS_EXT_DRUG_STRENGTH = FHIR_OPENMRS_FHIR_EXT_MEDICINE + "#strength";

    public static final String FHIR_OPENMRS_EXT_ADDRESS = FHIR_OPENMRS_SYSTEM_PREFIX + "/address";

    public static final String FHIR_OPENMRS_EXT_ADDRESS1 = FHIR_OPENMRS_EXT_ADDRESS + "#address1";

    public static final String FHIR_OPENMRS_EXT_ADDRESS2 = FHIR_OPENMRS_EXT_ADDRESS + "#address2";

    public static final String MODEL_EXTERNAL_IDENTIFIER = "ir.model.data";

    public static final String MODEL_PRODUCT = "product.product";

    public static final String MODEL_COMPANY = "res.company";

    public static final String MODEL_PRODUCT_CATEGORY = "product.category";

    public static final String MODEL_CURRENCY = "res.currency";

    public static final String PRODUCT_TYPE_STORABLE = "product";

    public static final String MODEL_PARTNER = "res.partner";

    public static final String MODEL_FHIR_PATIENT = "patient";

    public static final String MODEL_COUNTRY_STATE = "res.country.state";

    public static final String MODEL_COUNTRY = "res.country";

    public static final String MODEL_FHIR_ENCOUNTER = "encounter";

    public static final String MODEL_FHIR_SERVICE_REQUEST = "servicerequest";

    public static final String MODEL_SALE_ORDER = "sale.order";

    public static final String MODEL_SALE_ORDER_LINE = "sale.order.line";

    public static final String MODEL_WAREHOUSE = "stock.warehouse";

    public static final String MODEL_STOCK_QUANT = "stock.quant";

    /** Initializer XML-id module used for OpenMRS location UUID → res.company. */
    public static final String INIT_MODULE = "init";

    public static final String LOINC_SOURCE = "http://loinc.org";

    public static final String IDENTIFIER_FACILITY_ID_SYSTEM = "http://openelis-global.org/facility_id";
}
