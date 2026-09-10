/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.handlers.openmrs;

import lombok.Setter;
import lombok.extern.slf4j.Slf4j;
import org.hl7.fhir.r4.model.Encounter;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Slf4j
@Setter
@Component
public class VisitLocationResolver {

    @Autowired
    private EncounterHandler encounterHandler;

    /**
     * OpenMRS location UUID for the visit linked to a clinical encounter (via {@code partOf}).
     * Used as {@code company_external_id} for Odoo inventory dispense.
     */
    public String resolveLocationUuid(Encounter encounter) {
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

    static String extractVisitEncounterUuid(Encounter encounter) {
        if (encounter == null || !encounter.hasPartOf() || !encounter.getPartOf().hasReference()) {
            return null;
        }
        String ref = encounter.getPartOf().getReference();
        if (ref == null || !ref.contains("/")) {
            return null;
        }
        return ref.split("/")[1];
    }
}
