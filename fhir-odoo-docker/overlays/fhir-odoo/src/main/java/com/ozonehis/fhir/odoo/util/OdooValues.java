/*
 * Copyright © 2024, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.fhir.odoo.util;

import ca.uhn.fhir.rest.param.TokenAndListParam;
import java.util.ArrayList;
import java.util.List;

public final class OdooValues {

    private OdooValues() {}

    public static Integer asInteger(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Integer i) {
            return i;
        }
        if (value instanceof Number n) {
            return n.intValue();
        }
        if (value instanceof Boolean) {
            return null;
        }
        if (value instanceof Object[] arr && arr.length > 0) {
            return asInteger(arr[0]);
        }
        if (value instanceof List<?> list && !list.isEmpty()) {
            return asInteger(list.get(0));
        }
        return null;
    }

    public static double asDouble(Object value) {
        if (value == null) {
            return 0d;
        }
        if (value instanceof Number n) {
            return n.doubleValue();
        }
        return 0d;
    }

    public static List<String> tokenValues(TokenAndListParam param) {
        List<String> values = new ArrayList<>();
        if (param == null) {
            return values;
        }
        param.getValuesAsQueryTokens().forEach(orList -> orList.getValuesAsQueryTokens().forEach(token -> {
            if (token.getValue() != null && !token.getValue().isBlank()) {
                values.add(token.getValue());
            }
        }));
        return values;
    }

    public static String firstTokenValue(TokenAndListParam param) {
        List<String> values = tokenValues(param);
        return values.isEmpty() ? null : values.get(0);
    }
}
