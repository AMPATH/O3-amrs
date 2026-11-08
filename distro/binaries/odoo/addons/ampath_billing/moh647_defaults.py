# -*- coding: utf-8 -*-
"""Default MOH 647 tracer → product links.

Resolved at install/upgrade by default_code (preferred) or exact product name.
All 85 tracers always appear on the mapping screen.

MOH647_UNMAPPED_SEQUENCES only skips *automatic* default seeding (no product found
or intentionally left for manual map). Users can still map any product, then use
Apply related drugs for same-GE siblings. Report A–J stays '-' until mapped:

  32 Penicillin V 250mg
  67 Dryview DVE
  68 Anti-Human Globulin
  69 Bovine Albumin
  73 Distilled water
  79 Lugol's iodine
  40 Bin Liners (yellow) — only red liners found in catalogue
"""

# sequence -> list of default_code values (first match wins; all found are linked)
MOH647_CODES_BY_SEQUENCE = {
    2: ['PM03ALB007'],
    5: [],  # prefer exact name below
    6: ['PM06ATV002'],
    8: ['PM07CAR004'],
    9: ['PM01CEF002'],
    11: ['PM12CLD003'],
    13: ['PM07FLX001'],
    14: ['PM01GEN001'],  # closest stocked gentamicin amp; verify 80mg/2ml
    26: ['PM02NYS001'],
    33: ['EM06NEB005'],
    35: ['PD01SHS009'],
    38: [],  # name match
    39: ['NM01BAN001'],
    41: ['NM02CAT014'],
    42: ['NM19MAT006'],
    43: ['NM01GAU002'],
    44: ['NM01CTW001'],
    45: ['NM07GLV001'],
    47: ['NM10SYR041'],
    48: ['NM08CAN002'],
    49: ['NM08CAN003'],
    50: ['NM09SET001'],
    51: ['NM19MAT005'],
    52: ['NM20RES011'],
    53: ['NM20RES010'],
    54: ['NM05TUB016'],
    55: ['NM11BXS001'],
    56: ['NM09SET002'],
    57: ['NM03SCA016'],
    58: ['NM06BLA002'],
    59: ['NM03SUT145'],
    60: ['NM03SUT097'],
    63: ['NM10SYR039'],
    64: ['NM10SYR038'],
    65: ['NM01ZNS003'],
    66: ['NX01FLM024'],
    70: ['NL01BGS001'],
    71: ['NL01BGS002'],
    72: ['NL01BGS004'],
    74: ['PD01FDE001'],
    75: ['NL08BLB029'],
    76: ['NL08LBL051'],
    77: ['NL05TES094'],
    78: ['EM03HBM003', 'NL08CVT001'],
    81: ['NL05TES119'],
    84: ['FS4005-1'],
    85: ['PM14RET008'],  # catalogue has 200000 IU
}

# sequence -> exact product name (case-insensitive) when no reliable default_code
MOH647_NAMES_BY_SEQUENCE = {
    1: ['ADRENALINE INJECTION - 1MG/ML', 'ADRENALINE 1mg/ml'],
    3: ['AMLODIPINE 5mg TAB', 'AMLODIPINE TABLET 5MG'],
    4: ['AMOXICILLIN 500mg CAP'],
    5: ['AMOXICILLIN DISPERSIBLE SCORED TAB 250MG', 'AMOXICILLIN DISPERSIBLE SCORED TAB 250 MG'],
    7: ['BENZYL PENICILLIN 1MU REC INJ'],
    10: ['CETIRIZINE 10mg TAB'],
    12: ['CHLORPHENAMINE 2mg/5ml SYR', 'Chlorpheniramine'],
    15: ['GLICLAZIDE 40mg'],
    16: ['HALOPERIDOL 5mg TAB'],
    17: ['HYDROCORTISONE 100mg SOL INJ'],
    18: ['HYDROXYCARBAMIDE (HYDROXYUREA) CAPSULE 500 MG'],
    19: [
        'INSULIN (PREMIX) RECOMBINANT HUMAN ( 30 REGULAR + 70 NPH) ALSO CALLED BIPHASIC ( 30/70) 100 IU/ML -10ML VIAL',
        'INSULIN (MIXTARD) 70/30 100IU/ML INJ',
    ],
    20: ['LIDOCAINE 2% INJ', 'LIDOCAINE 2% SOL INJ'],
    21: ['Losartan-H (3 x 10` s)', 'LOSARTAN 50mg AND HYDROCHLOROTHIAZIDE 12.5mg'],
    22: ['MAGNESIUM SULPHATE INJECTION - 50%'],
    23: ['METFORMIN 500mg TAB'],
    24: ['METRONIDAZOLE 200mg TAB'],
    25: ['MIDAZOLAM INJECTION 1MG/1ML- 5ML AMPOULE'],
    27: ['Omeprazole 20mg'],
    28: [
        'CO-PACK OF 4 SATCHETS OF LOW OSMOLARITY ORS (500ML FORMULATION) + 10 TABLETS OF DISPERSIBLE ZINC SULPHATE TABLETS 20MG',
        'CO-PACK OF 4 SATCHETS OF LOW OSMOLARITY ORS (500ML FORMULATION)+10 TABLETS OF DISPERSIBLE ZINC SULPHATE TABLETS 20MG',
    ],
    29: ['OXYTOCIN 10iu SOL INJ', 'OXYTOCIN INJECTION - 10 IU/ML'],
    30: ['PARACETAMOL 120mg/5ml SUSP'],
    31: ['PARACETAMOL 500mg TAB'],
    34: ['SODIUM CHLORIDE /NORMAL SALINE SOLUTION - 0.9% EURO CAP BOTTLE', 'NORMAL SALINE 0.9% SOL INJ'],
    36: ['INSULIN (ACTRAPID) 100IU/ML INJ', 'Actrapid (1x10ml)'],
    37: ['TETRACYCLINE EYE OINTMENT -1%', 'TETRACYCLINE EYE OINTMENT-1%'],
    38: ['AUTOCLAVING TAPE - ¾ ( 19MM X 150M)'],
    46: ['SURGICAL GLOVES 7.5'],
    61: ['SYRINGES 2PC- 2ML RUP WITH G23 NEEDLE X 1', '2cc (2ml) SYRINGE'],
    62: ['SYRINGES 2PC - 5ML RUP WITH G 21NEEDLE X 11/2', '5cc (5ml) SYRINGE'],
    80: ['PREGNANCY TEST STRIP'],
    83: [
        'FERROUS SULP/FOLIC ACID TABLETS 200MG/400MG BLISTER PACK',
        'FERROUS SULPH./FOLIC ACID TABLETS 200MG/400MCG BLISTER PACK',
    ],
}

# Intentionally unmapped until catalogue products are identified
MOH647_UNMAPPED_SEQUENCES = {32, 40, 67, 68, 69, 73, 79}
