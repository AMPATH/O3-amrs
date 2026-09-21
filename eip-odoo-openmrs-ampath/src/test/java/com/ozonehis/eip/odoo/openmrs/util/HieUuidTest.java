/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.util;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class HieUuidTest {

    @Test
    void unitUuidMatchesPythonUuid5Dns() {
        // python: uuid.uuid5(uuid.NAMESPACE_DNS, "hie:unit:UM10001")
        assertEquals("6f9f4b4d-9288-5424-95a3-a3c211447ea7", HieUuid.forUnit("UM10001"));
    }

    @Test
    void geUuidMatchesPythonUuid5Dns() {
        assertEquals("578c4ee7-ca63-5d60-9b5d-51df0fac6587", HieUuid.forGe("GE10002"));
    }

    @Test
    void formUuidMatchesPythonUuid5Dns() {
        assertEquals("5377bf1b-c8b7-59ee-ae53-16786de8618a", HieUuid.forForm("DF10501"));
    }

    @Test
    void unitUuidIsStableAcrossCalls() {
        assertEquals(HieUuid.forUnit("tablet"), HieUuid.forUnit("tablet"));
    }
}
