/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.handlers.openmrs;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class HieOpenmrsCatalogueWriterTest {

    @Test
    void disambiguateAppendsCodeWhenDescriptionDiffers() {
        assertEquals("Bottle (DF10001)", HieOpenmrsCatalogueWriter.disambiguateConceptName("DF10001", "Bottle"));
        assertEquals("tablet (UM415)", HieOpenmrsCatalogueWriter.disambiguateConceptName("UM415", "tablet"));
    }

    @Test
    void disambiguateSkipsWhenCodeAlreadyPresent() {
        assertEquals("Bottle (DF10001)", HieOpenmrsCatalogueWriter.disambiguateConceptName("DF10001", "Bottle (DF10001)"));
        assertEquals("DF10001", HieOpenmrsCatalogueWriter.disambiguateConceptName("DF10001", "DF10001"));
    }

    @Test
    void disambiguateFallsBackToCode() {
        assertEquals("UM415", HieOpenmrsCatalogueWriter.disambiguateConceptName("UM415", null));
        assertEquals("UM415", HieOpenmrsCatalogueWriter.disambiguateConceptName("UM415", "  "));
    }

    @Test
    void isDuplicateConceptNameDetectsOpenMrsPayload() {
        Exception e = new Exception(
                "Request to OpenMRS failed with status code: 500, {\"error\":{\"message\":\"['Bottle' is a duplicate name in locale 'en']\",\"code\":\"org.openmrs.validator.ConceptValidator:183\"}}");
        assertTrue(HieOpenmrsCatalogueWriter.isDuplicateConceptName(e));
        assertFalse(HieOpenmrsCatalogueWriter.isDuplicateConceptName(new Exception("connection refused")));
    }
}
