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
import com.ozonehis.eip.odoo.openmrs.model.Company;
import java.util.List;
import java.util.Map;
import lombok.Setter;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Slf4j
@Setter
@Component
public class CompanyHandler {

    @Value("${odoo.company.location.field:x_location_uuid}")
    private String companyLocationField;

    @Autowired
    private OdooClient odooClient;

    @Autowired
    private OdooUtils odooUtils;

    /**
     * Look up an Odoo company whose {@code x_location_uuid} (or the field configured via
     * {@code odoo.company.location.field}) matches the given OpenMRS location UUID.
     *
     * @param locationUuid the OpenMRS location UUID extracted from the FHIR Encounter
     * @return the matching {@link Company}, or {@code null} if none found or the field is not configured
     */
    public Company getCompanyByLocationUuid(String locationUuid) {
        if (locationUuid == null || locationUuid.isBlank()) {
            return null;
        }
        try {
            Object[] records = odooClient.searchAndRead(
                    Constants.COMPANY_MODEL,
                    List.of(asList(companyLocationField, "=", locationUuid)),
                    asList("id", "name", companyLocationField));
            if (records == null || records.length == 0) {
                log.warn("No Odoo company found for OpenMRS location UUID '{}'", locationUuid);
                return null;
            }
            if (records.length > 1) {
                log.warn(
                        "Multiple Odoo companies found for OpenMRS location UUID '{}'; using the first one",
                        locationUuid);
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> record = (Map<String, Object>) records[0];
            return odooUtils.convertToObject(record, Company.class);
        } catch (Exception e) {
            log.warn(
                    "Failed to look up Odoo company by location UUID '{}' (field '{}'): {}",
                    locationUuid,
                    companyLocationField,
                    e.getMessage());
            return null;
        }
    }
}
