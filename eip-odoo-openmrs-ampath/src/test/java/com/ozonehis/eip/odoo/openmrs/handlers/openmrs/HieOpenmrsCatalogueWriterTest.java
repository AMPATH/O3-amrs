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
    void disambiguateConceptName_appendsCodeWhenDistinct() {
        assertEquals("Tablet (DF10501)", HieOpenmrsCatalogueWriter.disambiguateConceptName("DF10501", "Tablet"));
        assertEquals("Bottle (DF10001)", HieOpenmrsCatalogueWriter.disambiguateConceptName("DF10001", "Bottle"));
    }

    @Test
    void disambiguateConceptName_skipsWhenCodeAlreadyPresent() {
        assertEquals("Tablet (DF10501)", HieOpenmrsCatalogueWriter.disambiguateConceptName("DF10501", "Tablet (DF10501)"));
        assertEquals("DF10501", HieOpenmrsCatalogueWriter.disambiguateConceptName("DF10501", "DF10501"));
    }

    @Test
    void isDuplicateConceptName_detectsOpenmrsMessage() {
        Exception nested = new Exception("Concept name 'Tablet' is a duplicate name");
        Exception wrapper = new RuntimeException("create failed", nested);
        assertTrue(HieOpenmrsCatalogueWriter.isDuplicateConceptName(wrapper));
        assertFalse(HieOpenmrsCatalogueWriter.isDuplicateConceptName(new RuntimeException("unrelated")));
    }
}
