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
import org.springframework.stereotype.Component;

/**
 * Resolves an Odoo company from an OpenMRS location UUID.
 *
 * <p>Convention: every Odoo company that maps to an OpenMRS location must be given an external ID
 * of the form {@code init.<location-uuid>} in the initializer CSV, e.g.:
 * <pre>
 *   "init.090089ea-1352-11df-a1f1-0026b9348838","Kesses","base.KES",...
 * </pre>
 * EIP then resolves the location UUID directly via {@code ir.model.data} with no custom fields and
 * no restart required. To add a new company, simply add a new CSV row with
 * {@code id = init.<location-uuid>}.
 */
@Slf4j
@Setter
@Component
public class CompanyHandler {

    private static final String INIT_MODULE = "init";

    @Autowired
    private OdooClient odooClient;

    @Autowired
    private OdooUtils odooUtils;

    /**
     * Returns the Odoo company whose external ID name equals the given OpenMRS location UUID
     * (module {@code init}), or {@code null} if no such company exists (the sale order will then
     * fall back to the user's default company).
     */
    public Company getCompanyByLocationUuid(String locationUuid) {
        if (locationUuid == null || locationUuid.isBlank()) {
            return null;
        }
        try {
            Object[] imdRecords = odooClient.searchAndRead(
                    Constants.IR_MODEL,
                    List.of(
                            asList("module", "=", INIT_MODULE),
                            asList("name", "=", locationUuid),
                            asList("model", "=", "res.company")),
                    asList("id", "res_id"));

            if (imdRecords == null || imdRecords.length == 0) {
                log.debug("No Odoo company has external ID 'init.{}' — using default company", locationUuid);
                return null;
            }

            @SuppressWarnings("unchecked")
            int companyResId = (int) ((Map<String, Object>) imdRecords[0]).get("res_id");

            Object[] companyRecords = odooClient.searchAndRead(
                    Constants.COMPANY_MODEL,
                    List.of(asList("id", "=", companyResId)),
                    asList("id", "name"));

            Company company = new Company();
            company.setCompanyId(companyResId);
            if (companyRecords != null && companyRecords.length > 0) {
                @SuppressWarnings("unchecked")
                String name = (String) ((Map<String, Object>) companyRecords[0]).get("name");
                company.setCompanyName(name);
            }

            log.debug("Resolved location UUID '{}' → company '{}' (id={})",
                    locationUuid, company.getCompanyName(), companyResId);
            return company;

        } catch (Exception e) {
            log.warn("Failed to resolve company for location UUID '{}': {}", locationUuid, e.getMessage());
            return null;
        }
    }
}
