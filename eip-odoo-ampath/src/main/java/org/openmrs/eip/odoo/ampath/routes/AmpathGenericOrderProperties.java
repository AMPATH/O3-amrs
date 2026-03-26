package org.openmrs.eip.odoo.ampath.routes;


import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

import org.springframework.stereotype.Component;

/**
 * Provides the set of order-type UUIDs that GenericOrderRouting should process.
 * Hardcoded to the standard Radiology + Procedure + Consultation UUIDs used at AMPATH.
 */
@Component
public class AmpathGenericOrderProperties {

    private static final String DEFAULT_UUIDS =
            "ff4485a4-f071-4423-aeb2-db6efce52b83,2315ab24-9a4e-4b36-b189-8e74d2c77394,2da15461-81db-43bc-a2c0-853741bece90";

    private final Set<String> uuidSet;

    public AmpathGenericOrderProperties() {
        Set<String> set = new HashSet<>();
        for (String uuid : DEFAULT_UUIDS.split(",")) {
            String trimmed = uuid.trim();
            if (!trimmed.isEmpty()) {
                set.add(trimmed);
            }
        }
        uuidSet = Collections.unmodifiableSet(set);
    }

    public boolean isGenericOrderHandlingEnabled() {
        return !uuidSet.isEmpty();
    }

    public Set<String> getGenericOrderTypeUuids() {
        return uuidSet;
    }

    public String getEffectiveRawUuids() {
        return DEFAULT_UUIDS;
    }
}

