/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.util;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.UUID;

/**
 * Deterministic UUID5 helpers for HIE catalogue identities shared across OpenMRS and Odoo.
 */
public final class HieUuid {

    /** DNS namespace — same as {@code uuid.NAMESPACE_DNS} in Python. */
    public static final UUID NAMESPACE_DNS = UUID.fromString("6ba7b810-9dad-11d1-80b4-00c04fd430c8");

    public static final String GE_PREFIX = "hie:ge:";
    public static final String FORM_PREFIX = "hie:form:";
    public static final String ROUTE_PREFIX = "hie:route:";
    public static final String UNIT_PREFIX = "hie:unit:";

    private HieUuid() {}

    public static UUID uuid5(String name) {
        return uuid5(NAMESPACE_DNS, name);
    }

    public static UUID uuid5(UUID namespace, String name) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-1");
            md.update(uuidToBytes(namespace));
            md.update(name.getBytes(StandardCharsets.UTF_8));
            byte[] digest = md.digest();
            digest[6] &= 0x0f;
            digest[6] |= 0x50; // version 5
            digest[8] &= 0x3f;
            digest[8] |= 0x80; // IETF variant
            ByteBuffer buffer = ByteBuffer.wrap(digest, 0, 16);
            return new UUID(buffer.getLong(), buffer.getLong());
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-1 not available", e);
        }
    }

    public static String forGe(String geCode) {
        return uuid5(GE_PREFIX + geCode).toString();
    }

    public static String forForm(String formCode) {
        return uuid5(FORM_PREFIX + formCode).toString();
    }

    public static String forRoute(String routeCode) {
        return uuid5(ROUTE_PREFIX + routeCode).toString();
    }

    public static String forUnit(String unitCode) {
        return uuid5(UNIT_PREFIX + unitCode).toString();
    }

    private static byte[] uuidToBytes(UUID uuid) {
        ByteBuffer buffer = ByteBuffer.wrap(new byte[16]);
        buffer.putLong(uuid.getMostSignificantBits());
        buffer.putLong(uuid.getLeastSignificantBits());
        return buffer.array();
    }
}
