/*
 * Copyright © 2024, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.fhir.odoo.model;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.io.Serial;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
@EqualsAndHashCode(callSuper = true)
@JsonIgnoreProperties(ignoreUnknown = true)
public class Product extends BaseOdooModel {

    @Serial
    private static final long serialVersionUID = 1L;

    @JsonProperty("description")
    private String description;

    @JsonProperty("uom_name")
    private String uomName;

    // Quantity on hand
    @JsonProperty("qty_available")
    private Double quantityAvailable;

    @JsonProperty("list_price")
    private Double listPrice;

    @JsonProperty("lst_price")
    private Double publicPrice;

    @JsonProperty("standard_price")
    private Double standardPrice;

    @JsonProperty("active")
    @JsonFormat(shape = JsonFormat.Shape.BOOLEAN)
    private boolean active;

    @JsonProperty("code")
    private String code;

    @JsonProperty("currency_id")
    private Integer currencyId;

    @JsonProperty("type")
    private String type;

    @JsonProperty("x_concept_source")
    private String conceptSource;

    @JsonProperty("x_concept_code")
    private String conceptCode;

    @JsonProperty("x_drug_strength")
    private String drugStrength;

    @JsonProperty("x_openmrs_drug_uuid")
    private String openmrsDrugUuid;
}
