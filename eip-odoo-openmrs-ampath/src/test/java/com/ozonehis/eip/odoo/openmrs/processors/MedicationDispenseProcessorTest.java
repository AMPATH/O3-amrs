/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.processors;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.hl7.fhir.r4.model.MedicationDispense;
import org.hl7.fhir.r4.model.Quantity;
import org.hl7.fhir.r4.model.Reference;
import org.junit.jupiter.api.Test;

class MedicationDispenseProcessorTest {

    @Test
    void completedStatusIsDispensable() {
        MedicationDispense dispense = sampleDispense();
        dispense.setStatus(MedicationDispense.MedicationDispenseStatus.COMPLETED);
        assertTrue(MedicationDispenseProcessor.isCompleted(dispense));
        assertFalse(MedicationDispenseProcessor.shouldReverse(dispense));
    }

    @Test
    void cancelledStatusShouldReverse() {
        MedicationDispense dispense = sampleDispense();
        dispense.setStatus(MedicationDispense.MedicationDispenseStatus.CANCELLED);
        assertTrue(MedicationDispenseProcessor.shouldReverse(dispense));
    }

    @Test
    void enteredInErrorShouldReverse() {
        MedicationDispense dispense = sampleDispense();
        dispense.setStatus(MedicationDispense.MedicationDispenseStatus.ENTEREDINERROR);
        assertTrue(MedicationDispenseProcessor.shouldReverse(dispense));
    }

    @Test
    void preparationStatusIsSkipped() {
        MedicationDispense dispense = sampleDispense();
        dispense.setStatus(MedicationDispense.MedicationDispenseStatus.PREPARATION);
        assertFalse(MedicationDispenseProcessor.isCompleted(dispense));
        assertFalse(MedicationDispenseProcessor.shouldReverse(dispense));
    }

    @Test
    void buildPayloadFromDispenseResource() {
        MedicationDispense dispense = sampleDispense();
        var payload = MedicationDispenseProcessor.buildDispensePayload(dispense);
        assertEquals("8d0194ed-84cb-4345-b85a-63a5b73fa5e4", payload.openmrsDrugUuid());
        assertEquals(10.0, payload.quantity());
        assertEquals("18c343eb-b353-462a-9139-b16606e6b6c2", payload.companyExternalId());
        assertEquals("260bb53f-a0c2-49c7-af79-2721c15699e0", payload.patientExternalId());
        assertEquals(null, payload.lotId());
        assertEquals(null, payload.quantityUnitUuid());
    }

    @Test
    void rejectMissingQuantity() {
        MedicationDispense dispense = sampleDispense();
        dispense.setQuantity(null);
        assertThrows(IllegalArgumentException.class, () -> MedicationDispenseProcessor.resolveQuantity(dispense));
    }

    @Test
    void rejectMissingLocation() {
        MedicationDispense dispense = sampleDispense();
        dispense.setLocation(null);
        assertThrows(
                IllegalArgumentException.class, () -> MedicationDispenseProcessor.buildDispensePayload(dispense));
    }

    private static MedicationDispense sampleDispense() {
        MedicationDispense dispense = new MedicationDispense();
        dispense.setId("dispense-uuid-1");
        dispense.setStatus(MedicationDispense.MedicationDispenseStatus.COMPLETED);
        dispense.setMedication(new Reference("Medication/8d0194ed-84cb-4345-b85a-63a5b73fa5e4"));
        dispense.setSubject(new Reference("Patient/260bb53f-a0c2-49c7-af79-2721c15699e0"));
        dispense.setLocation(new Reference("Location/18c343eb-b353-462a-9139-b16606e6b6c2"));
        dispense.setQuantity(new Quantity().setValue(10).setUnit("TABLET, DOSAGE FORM"));
        return dispense;
    }
}
