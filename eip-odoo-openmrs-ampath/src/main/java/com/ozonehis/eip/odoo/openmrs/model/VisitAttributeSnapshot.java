/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.model;

import lombok.Value;

@Value
public class VisitAttributeSnapshot {

    String paymentMethod;
    String insuranceScheme;

    public static VisitAttributeSnapshot empty() {
        return new VisitAttributeSnapshot(null, null);
    }
}
