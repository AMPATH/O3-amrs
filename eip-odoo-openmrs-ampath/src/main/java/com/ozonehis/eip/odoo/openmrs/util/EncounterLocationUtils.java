/*
 * Copyright © 2021, Ozone HIS <info@ozonehis.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.util;

import org.hl7.fhir.r4.model.Encounter;

/** Utilities for OpenMRS / FHIR {@link Encounter} fields used in Odoo sync. */
public final class EncounterLocationUtils {

    private EncounterLocationUtils() {}

    /**
     * Returns the logical id (UUID) of the first {@link Encounter.EncounterLocationComponent}
     * with a location reference, e.g. {@code Location/abc-uuid} → {@code abc-uuid}.
     */
    public static String firstLocationUuid(Encounter encounter) {
        if (encounter == null || !encounter.hasLocation()) {
            return null;
        }
        for (Encounter.EncounterLocationComponent loc : encounter.getLocation()) {
            if (loc == null || !loc.hasLocation()) {
                continue;
            }
            String ref = loc.getLocation().getReference();
            if (ref == null || ref.isEmpty()) {
                continue;
            }
            int slash = ref.lastIndexOf('/');
            return slash >= 0 ? ref.substring(slash + 1) : ref;
        }
        return null;
    }
}
