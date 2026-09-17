/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.handlers.hie;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class HieProductCatalogueSynchronizerTest {

    @Test
    void buildSkuName_includesManufacturerWhenPresent() {
        assertEquals(
                "FOLIC (100's) [PH3885-1] — BIODEAL LABORATORIES LTD",
                HieProductCatalogueSynchronizer.buildSkuName(
                        "FOLIC",
                        "Folic Acid 5mg Tablet",
                        "100's",
                        "PH3885-1",
                        "BIODEAL LABORATORIES LTD"));
    }

    @Test
    void buildSkuName_omitsManufacturerWhenNull() {
        assertEquals(
                "FOLIC (100's) [PH3486-1]",
                HieProductCatalogueSynchronizer.buildSkuName(
                        "FOLIC", "Folic Acid 5mg Tablet", "100's", "PH3486-1", null));
    }

    @Test
    void buildSkuName_fallsBackToGenericWhenBrandMissing() {
        assertEquals(
                "Folic Acid 5mg Tablet (100's) [PH19092-1] — ZAIN PHARMA",
                HieProductCatalogueSynchronizer.buildSkuName(
                        null, "Folic Acid 5mg Tablet", "100's", "PH19092-1", "ZAIN PHARMA"));
    }
}
