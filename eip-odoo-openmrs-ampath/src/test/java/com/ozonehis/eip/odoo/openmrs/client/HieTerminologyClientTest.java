/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.client;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import org.junit.jupiter.api.Test;

class HieTerminologyClientTest {

    @Test
    void etcdProductIdFromPackageCode_stripsNumericPackSuffix() {
        assertEquals("PH3885", HieTerminologyClient.etcdProductIdFromPackageCode("PH3885-1"));
        assertEquals("PH18652", HieTerminologyClient.etcdProductIdFromPackageCode("PH18652-2"));
    }

    @Test
    void etcdProductIdFromPackageCode_keepsCodeWithoutNumericSuffix() {
        assertEquals("PH3885", HieTerminologyClient.etcdProductIdFromPackageCode("PH3885"));
        assertEquals("PH-ABC", HieTerminologyClient.etcdProductIdFromPackageCode("PH-ABC"));
    }

    @Test
    void etcdProductIdFromPackageCode_nullOrBlank() {
        assertNull(HieTerminologyClient.etcdProductIdFromPackageCode(null));
        assertNull(HieTerminologyClient.etcdProductIdFromPackageCode("  "));
    }
}
