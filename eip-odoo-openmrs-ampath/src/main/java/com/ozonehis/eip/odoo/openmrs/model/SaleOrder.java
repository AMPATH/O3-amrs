/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class SaleOrder implements OdooResource {

    @JsonProperty("id")
    private Integer orderId;

    @JsonProperty("client_order_ref")
    private String orderClientOrderRef;

    @JsonProperty("state")
    private String orderState;

    @JsonProperty("partner_id")
    private Object orderPartnerId; // Can be used as a list or Integer

    @JsonProperty("order_line")
    private List<Integer> orderLine;

    @JsonProperty("type_name")
    private String orderTypeName;

    @JsonProperty("odoo.customer.weight.field")
    private String partnerWeight;

    @JsonProperty("odoo.customer.dob.field")
    private String partnerBirthDate;

    @JsonProperty("odoo.customer.id.field")
    private String odooCustomerId;

    @JsonProperty("company_id")
    private Integer companyId;

    @JsonProperty("x_patient_uuid")
    private String patientUuid;

    @JsonProperty("x_payment_method")
    private String paymentMethod;

    @JsonProperty("x_insurance_scheme")
    private String insuranceScheme;

    @JsonProperty("x_preauth_fhir_claim_id")
    private String preauthFhirClaimId;

    @JsonProperty("x_sha_client_registry_id")
    private String shaClientRegistryId;

    @JsonProperty("x_sha_facility_id")
    private String shaFacilityId;

    @JsonProperty("x_sha_facility_name")
    private String shaFacilityName;

    @JsonProperty("x_sha_facility_level")
    private String shaFacilityLevel;

    @JsonProperty("x_coverage_id")
    private String coverageId;

    @JsonProperty("x_scheme_category_code")
    private String schemeCategoryCode;

    @JsonProperty("x_scheme_category_name")
    private String schemeCategoryName;

    @JsonProperty("x_claim_type")
    private String claimType;

    @JsonProperty("x_claim_sub_type")
    private String claimSubType;

    @JsonProperty("x_priority_code")
    private String priorityCode;

    @JsonProperty("x_claim_practitioner_id")
    private String claimPractitionerId;

    @JsonProperty("x_claim_diagnoses_json")
    private String claimDiagnosesJson;

    @JsonProperty("x_openmrs_encounter_uuid")
    private String openmrsEncounterUuid;

    @JsonProperty("x_patient_gender")
    private String patientGender;
}
