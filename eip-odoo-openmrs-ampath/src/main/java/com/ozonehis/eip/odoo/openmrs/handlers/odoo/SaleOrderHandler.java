/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.handlers.odoo;

import static java.util.Arrays.asList;

import com.ozonehis.eip.odoo.openmrs.Constants;
import com.ozonehis.eip.odoo.openmrs.client.OdooClient;
import com.ozonehis.eip.odoo.openmrs.client.OdooUtils;
import com.ozonehis.eip.odoo.openmrs.handlers.openmrs.VisitDiagnosisRestHandler;
import com.ozonehis.eip.odoo.openmrs.handlers.openmrs.EncounterHandler;
import com.ozonehis.eip.odoo.openmrs.handlers.openmrs.ObservationHandler;
import com.ozonehis.eip.odoo.openmrs.handlers.openmrs.PatientHandler;
import com.ozonehis.eip.odoo.openmrs.handlers.openmrs.VisitAttributeHandler;
import com.ozonehis.eip.odoo.openmrs.mapper.odoo.SaleOrderMapper;
import com.ozonehis.eip.odoo.openmrs.model.Company;
import com.ozonehis.eip.odoo.openmrs.model.Partner;
import com.ozonehis.eip.odoo.openmrs.model.Product;
import com.ozonehis.eip.odoo.openmrs.model.SaleOrder;
import com.ozonehis.eip.odoo.openmrs.model.SaleOrderLine;
import com.ozonehis.eip.odoo.openmrs.model.VisitAttributeSnapshot;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import lombok.Setter;
import lombok.extern.slf4j.Slf4j;
import org.apache.camel.ProducerTemplate;
import org.hl7.fhir.r4.model.Encounter;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Resource;
import org.openmrs.eip.EIPException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Slf4j
@Setter
@Component
public class SaleOrderHandler {

    @Value("${eip.weight.concept}")
    private String weightConcept;

    @Value("${odoo.customer.weight.field}")
    private String odooCustomerWeightField;

    @Value("${odoo.customer.dob.field}")
    private String odooCustomerDobField;

    @Value("${odoo.customer.id.field}")
    private String odooCustomerIdField;

    @Autowired
    private OdooClient odooClient;

    @Autowired
    private SaleOrderLineHandler saleOrderLineHandler;

    @Autowired
    private SaleOrderMapper saleOrderMapper;

    @Autowired
    private ProductHandler productHandler;

    @Autowired
    private ObservationHandler observationHandler;

    @Autowired
    private EncounterHandler encounterHandler;

    @Autowired
    private OdooUtils odooUtils;

    @Autowired
    private CompanyHandler companyHandler;

    @Autowired
    private VisitAttributeHandler visitAttributeHandler;

    @Autowired
    private VisitDiagnosisRestHandler visitDiagnosisRestHandler;

    @Autowired
    private PatientHandler patientHandler;

    public List<String> orderDefaultAttributes;

    public SaleOrder getDraftSaleOrderIfExistsByVisitId(String visitId) {
        List<String> baseOrderAttributes = asList("id", "client_order_ref", "partner_id", "state", "order_line");
        orderDefaultAttributes = asList(
                "id",
                "client_order_ref",
                "partner_id",
                "state",
                "order_line",
                odooCustomerWeightField,
                odooCustomerDobField,
                odooCustomerIdField);
        Object[] records;
        try {
            records = odooClient.searchAndRead(
                    Constants.SALE_ORDER_MODEL,
                    List.of(asList("client_order_ref", "=", visitId), asList("state", "=", "draft")),
                    orderDefaultAttributes);
        } catch (RuntimeException ex) {
            if (!isInvalidConfiguredSaleOrderFieldError(ex)) {
                throw ex;
            }
            log.warn(
                    "Configured optional sale.order field is missing (weight='{}', dob='{}', id='{}'). "
                            + "Retrying search_read with base fields only.",
                    odooCustomerWeightField,
                    odooCustomerDobField,
                    odooCustomerIdField);
            records = odooClient.searchAndRead(
                    Constants.SALE_ORDER_MODEL,
                    List.of(asList("client_order_ref", "=", visitId), asList("state", "=", "draft")),
                    baseOrderAttributes);
        }
        if (records == null) {
            throw new EIPException(
                    String.format("Got null response while fetching for Sale order with client_order_ref %s", visitId));
        } else if (records.length == 1) {
            @SuppressWarnings("unchecked")
            Map<String, Object> record = (Map<String, Object>) records[0];
            SaleOrder saleOrder = odooUtils.convertToObject(record, SaleOrder.class);
            log.debug("Sale order exists with client_order_ref {} sale order {}", visitId, saleOrder);
            return saleOrder;
        } else if (records.length == 0) {
            log.warn("No Sale order found with client_order_ref {}", visitId);
            return null;
        } else {
            log.warn("Multiple Sale order exists with client_order_ref {}", visitId);
            throw new EIPException(String.format("Multiple Sale order found with client_order_ref %s", visitId));
        }
    }

    public void sendSaleOrder(ProducerTemplate producerTemplate, String endpointUri, SaleOrder saleOrder) {
        Map<String, Object> saleOrderHeaders = new HashMap<>();
        if (endpointUri.contains("update")) {
            saleOrderHeaders.put(
                    com.ozonehis.eip.odoo.openmrs.Constants.HEADER_ODOO_ID_ATTRIBUTE_VALUE,
                    List.of(saleOrder.getOrderId()));
        }
        producerTemplate.sendBodyAndHeaders(endpointUri, saleOrder, saleOrderHeaders);
    }

    public void updateSaleOrderIfExistsWithSaleOrderLine(
            Resource resource,
            SaleOrder saleOrder,
            String encounterVisitUuid,
            int partnerId,
            String patientID,
            ProducerTemplate producerTemplate) {
        // If sale order exists create sale order line and link it to sale order
        SaleOrderLine saleOrderLine = saleOrderLineHandler.buildSaleOrderLineIfProductExists(resource, saleOrder);
        if (saleOrderLine == null) {
            log.info(
                    "{}: Skipping create sale order line for encounter Visit {}",
                    resource.getClass().getName(),
                    encounterVisitUuid);
            return;
        }

        // Update sale order with Patient Weight if not already present
        if (saleOrder.getPartnerWeight() == null
                || saleOrder.getPartnerWeight().isEmpty()
                || saleOrder.getPartnerWeight().equals("false")) {
            updateSaleOrderWithPatientWeight(partnerId, patientID, saleOrder, producerTemplate);
        }
        producerTemplate.sendBody("direct:odoo-create-sale-order-line-route", saleOrderLine);
        log.debug(
                "{}: Created sale order line {} and linked to sale order {}",
                resource.getClass().getName(),
                saleOrderLine,
                saleOrder);
        refreshVisitDiagnosesOnQuotation(encounterVisitUuid, saleOrder, partnerId, producerTemplate);
    }

    public void createSaleOrderWithSaleOrderLine(
            Resource resource,
            Encounter encounter,
            Partner partner,
            String encounterVisitUuid,
            String patientID,
            ProducerTemplate producerTemplate) {
        // If the sale order does not exist, create it, then create sale order line and link it to sale order
        SaleOrder newSaleOrder = saleOrderMapper.toOdoo(encounter);
        newSaleOrder.setOrderPartnerId(partner.getPartnerId());
        newSaleOrder.setOrderState("draft");
        // Add Patient DOB to Odoo Quotation
        newSaleOrder.setPartnerBirthDate(partner.getPartnerBirthDate());
        // Add Patient UUID (OpenMRS patient UUID) directly to the sale order
        newSaleOrder.setPatientUuid(patientID);
        // Add Patient Id to Odoo Quotation
        newSaleOrder.setOdooCustomerId(partner.getPartnerExternalId().replaceAll("(?i)</?p>", ""));
        String patientWeight = getPartnerWeight(patientID);
        if (patientWeight != null) {
            newSaleOrder.setPartnerWeight(getPartnerWeight(patientID));
        }
        // Resolve company from the visit location UUID
        String locationUuid = getVisitLocationUuid(encounter);
        if (locationUuid != null) {
            Company company = companyHandler.getCompanyByLocationUuid(locationUuid);
            if (company != null) {
                log.info(
                        "Assigning company '{}' (id={}) to sale order for encounter location UUID '{}'",
                        company.getCompanyName(),
                        company.getCompanyId(),
                        locationUuid);
                newSaleOrder.setCompanyId(company.getCompanyId());
            }
        }

        applyVisitBillingAttributes(encounter, newSaleOrder);
        applyClaimMetadataFromEncounter(encounter, newSaleOrder, patientID, encounterVisitUuid);

        sendSaleOrder(producerTemplate, "direct:odoo-create-sale-order-route", newSaleOrder);
        log.debug(
                "{}: Created sale order with partner_id {}", resource.getClass().getName(), partner.getPartnerId());

        SaleOrder fetchedSaleOrder = getDraftSaleOrderIfExistsByVisitId(encounterVisitUuid);
        if (fetchedSaleOrder != null) {
            SaleOrderLine saleOrderLine =
                    saleOrderLineHandler.buildSaleOrderLineIfProductExists(resource, fetchedSaleOrder);
            if (saleOrderLine == null) {
                log.info(
                        "{}: Skipping create sale order line and sale order for partner_id {}",
                        resource.getClass().getName(),
                        partner.getPartnerId());
                return;
            }

            producerTemplate.sendBody("direct:odoo-create-sale-order-line-route", saleOrderLine);
            log.debug(
                    "{}: Created sale order {} and sale order line {} and linked to sale order",
                    resource.getClass().getName(),
                    fetchedSaleOrder.getOrderId(),
                    saleOrderLine);
            refreshVisitDiagnosesOnQuotation(
                    encounterVisitUuid, fetchedSaleOrder, partner.getPartnerId(), producerTemplate);
        }
    }

    public void deleteSaleOrderLine(Resource resource, String encounterVisitUuid, ProducerTemplate producerTemplate) {
        SaleOrder saleOrder = getDraftSaleOrderIfExistsByVisitId(encounterVisitUuid);
        if (saleOrder != null) {
            Product product = productHandler.getProduct(resource);
            if (product != null) {
                SaleOrderLine saleOrderLine = saleOrderLineHandler.getSaleOrderLineIfExists(
                        saleOrder.getOrderId(), product.getProductResId());
                if (saleOrderLine != null) {
                    saleOrderLineHandler.sendSaleOrderLine(
                            producerTemplate, "direct:odoo-delete-sale-order-line-route", saleOrderLine);
                }
            }
        }
    }

    // Check if sale order has no sale order line, then cancel the sale order
    public void cancelSaleOrderWhenNoSaleOrderLine(
            int partnerId, String encounterVisitUuid, ProducerTemplate producerTemplate) {
        SaleOrder saleOrder = getDraftSaleOrderIfExistsByVisitId(encounterVisitUuid);
        if (saleOrder != null
                && (saleOrder.getOrderLine() == null || saleOrder.getOrderLine().isEmpty())) {
            log.debug("SaleOrderHandler: Count of sale order line {}", saleOrder.getOrderLine());
            saleOrder.setOrderState("cancel");
            saleOrder.setOrderPartnerId((Integer) partnerId);
            sendSaleOrder(producerTemplate, "direct:odoo-update-sale-order-route", saleOrder);
        }
    }

    public void updateSaleOrderWithPatientWeight(
            int partnerId, String patientID, SaleOrder saleOrder, ProducerTemplate producerTemplate) {
        String patientWeight = getPartnerWeight(patientID);
        if (saleOrder != null && patientWeight != null) {
            log.debug("SaleOrderHandler: Update sale order with Patient weight {}", saleOrder.getOrderId());
            saleOrder.setOrderPartnerId(partnerId);
            saleOrder.setPartnerWeight(patientWeight);
            sendSaleOrder(producerTemplate, "direct:odoo-update-sale-order-route", saleOrder);
        }
    }

    public String getPartnerWeight(String patientID) {
        Observation observation = observationHandler.getObservationBySubjectIDAndConceptID(patientID, weightConcept);
        if (observation == null) {
            return null;
        }

        return observation.getValueQuantity().getValue() + " "
                + observation.getValueQuantity().getUnit();
    }

    private boolean isInvalidConfiguredSaleOrderFieldError(RuntimeException ex) {
        String allMessages = allThrowableMessages(ex).toLowerCase();
        boolean invalidSaleOrderModel = allMessages.contains("on model 'sale.order'");
        boolean invalidWeightField = odooCustomerWeightField != null
                && !odooCustomerWeightField.isBlank()
                && allMessages.contains("invalid field '" + odooCustomerWeightField.toLowerCase() + "'");
        boolean invalidDobField = odooCustomerDobField != null
                && !odooCustomerDobField.isBlank()
                && allMessages.contains("invalid field '" + odooCustomerDobField.toLowerCase() + "'");
        boolean invalidIdField = odooCustomerIdField != null
                && !odooCustomerIdField.isBlank()
                && allMessages.contains("invalid field '" + odooCustomerIdField.toLowerCase() + "'");
        return invalidSaleOrderModel && (invalidWeightField || invalidDobField || invalidIdField);
    }

    /** OpenMRS visit encounter UUID from a clinical encounter's {@code partOf}, if present. */
    private static String extractVisitEncounterUuid(Encounter encounter) {
        if (encounter == null || !encounter.hasPartOf() || !encounter.getPartOf().hasReference()) {
            return null;
        }
        String ref = encounter.getPartOf().getReference();
        if (ref == null || !ref.contains("/")) {
            return null;
        }
        return ref.split("/")[1];
    }

    /** Sync OpenMRS visit attributes (payment method, scheme) from the visit encounter. */
    private void applyVisitBillingAttributes(Encounter encounter, SaleOrder saleOrder) {
        String visitUuid = extractVisitEncounterUuid(encounter);
        if (visitUuid == null) {
            return;
        }
        VisitAttributeSnapshot snap = visitAttributeHandler.readFromVisitEncounter(visitUuid);
        if (snap.getPaymentMethod() != null && !snap.getPaymentMethod().isBlank()) {
            saleOrder.setPaymentMethod(snap.getPaymentMethod());
        }
        if (snap.getInsuranceScheme() != null && !snap.getInsuranceScheme().isBlank()) {
            saleOrder.setInsuranceScheme(snap.getInsuranceScheme());
        }
    }

    /**
     * Populates quotation fields used for SHA pre-auth / claims (diagnoses, encounter link, patient gender)
     * without pulling bill details from OpenMRS cashier. Diagnoses are loaded for the whole visit (visit
     * encounter + child encounters), not only the triggering clinical encounter.
     */
    private void applyClaimMetadataFromEncounter(
            Encounter encounter, SaleOrder saleOrder, String patientId, String visitEncounterUuidForDiagnoses) {
        if (encounter != null
                && encounter.getIdElement() != null
                && encounter.getIdElement().hasIdPart()) {
            String encUuid = encounter.getIdElement().getIdPart();
            if (!encUuid.isBlank()) {
                saleOrder.setOpenmrsEncounterUuid(encUuid);
            }
        }
        String visitUuid = visitEncounterUuidForDiagnoses;
        if (visitUuid == null || visitUuid.isBlank()) {
            visitUuid = extractVisitEncounterUuid(encounter);
        }
        if (visitUuid != null && !visitUuid.isBlank()) {
            String json = visitDiagnosisRestHandler.buildDiagnosesJsonForVisit(visitUuid);
            if (json != null) {
                saleOrder.setClaimDiagnosesJson(json);
            }
        }
        try {
            if (patientId != null && !patientId.isBlank()) {
                Patient p = patientHandler.getPatientByPatientID(patientId);
                if (p != null && p.hasGender()) {
                    saleOrder.setPatientGender(p.getGender().toCode());
                }
            }
        } catch (Exception e) {
            log.debug("Could not load FHIR Patient for gender {}: {}", patientId, e.getMessage());
        }
    }

    /**
     * Re-fetch all visit diagnoses from OpenMRS FHIR and write {@code x_claim_diagnoses_json} on the draft
     * quotation (e.g. after a new order line is added so newly charted diagnoses are included).
     */
    public void refreshVisitDiagnosesOnQuotation(
            String visitEncounterUuid, SaleOrder saleOrder, int partnerId, ProducerTemplate producerTemplate) {
        if (visitEncounterUuid == null
                || visitEncounterUuid.isBlank()
                || saleOrder.getOrderId() == null) {
            return;
        }
        String json = visitDiagnosisRestHandler.buildDiagnosesJsonForVisit(visitEncounterUuid);
        if (json == null) {
            return;
        }
        SaleOrder patch = new SaleOrder();
        patch.setOrderId(saleOrder.getOrderId());
        patch.setOrderPartnerId(partnerId);
        patch.setClaimDiagnosesJson(json);
        sendSaleOrder(producerTemplate, "direct:odoo-update-sale-order-route", patch);
    }

    private String getVisitLocationUuid(Encounter encounter) {
        if (encounter == null || !encounter.hasPartOf()) {
            return null;
        }
        try {
            String visitUuid = extractVisitEncounterUuid(encounter);
            if (visitUuid == null) {
                return null;
            }
            Encounter visitEncounter = encounterHandler.getEncounterByEncounterID(visitUuid);
            if (visitEncounter == null
                    || visitEncounter.getLocation() == null
                    || visitEncounter.getLocation().isEmpty()) {
                log.warn("Visit encounter '{}' has no location set", visitUuid);
                return null;
            }
            String reference = visitEncounter.getLocation().get(0).getLocation().getReference();
            if (reference == null || !reference.contains("/")) {
                return null;
            }
            String locationUuid = reference.split("/")[1];
            log.debug("Resolved visit location UUID '{}' from visit '{}'", locationUuid, visitUuid);
            return locationUuid;
        } catch (Exception e) {
            log.warn("Failed to fetch visit location from encounter partOf reference: {}", e.getMessage());
            return null;
        }
    }

    private String allThrowableMessages(Throwable throwable) {
        StringBuilder all = new StringBuilder();
        Throwable current = throwable;
        while (current != null) {
            String message = current.getMessage();
            if (message != null) {
                all.append(message).append(' ');
            }
            current = current.getCause();
        }
        return all.toString();
    }
}
