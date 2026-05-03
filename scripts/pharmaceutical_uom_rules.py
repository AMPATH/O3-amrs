# -*- coding: utf-8 -*-
"""Map pharmaceutical product display names to Odoo initializer ``product.uom`` XML ids.

See ``distro/config/odoo/initializer_config/units_of_measure/product.uom.csv``.
"""
from __future__ import annotations

import re

# product.uom csv ids (AMPATH / OpenMRS-style)
UOM_TABLET = "init.a8a07f8e-1350-11df-a1f1-0026b9348838"
UOM_CAPSULE = "init.a8a0810a-1350-11df-a1f1-0026b9348838"
UOM_NUMBER_TABLETS = "init.a8a0630a-1350-11df-a1f1-0026b9348838"
UOM_SOLUTION_FOR_INJECTION = "init.e5e1fa57-2b8b-4aef-9b8c-8378b5382791"
UOM_SOLUTION = "init.0af16f27-aaa0-4bb1-b1a6-43734dab1a5c"
UOM_SYRUP = "init.a8a07ed0-1350-11df-a1f1-0026b9348838"
UOM_ORAL_SUSPENSION = "init.08709444-ac83-4af2-a8e5-86d91bb565b3"
UOM_DROPS = "init.3fbfabc6-9e78-4c70-85ee-8e66fc2418c5"
UOM_CREAM = "init.2c731799-e52f-40cd-864d-fb12a89a1f81"
UOM_OINTMENT = "init.89791287-a474-4a34-b8a5-7357da93ebec"
UOM_LOTION = "init.20f05920-0a4f-4708-af09-b20fe7185576"
UOM_SUPPOSITORY = "init.5185e5be-74af-43d1-ab6e-8bacdb835d5c"
UOM_POWDER = "init.a8a0804c-1350-11df-a1f1-0026b9348838"
UOM_PESSARY = "init.3392d4ed-88e1-46b4-bc17-9e8d332bc364"
UOM_MD_INHALER = "init.56624b7a-6f24-40aa-af30-cad799d110c5"
UOM_ML = "init.2952c978-5d2a-470b-b11b-0f50b23f752f"

_RE_INJECTABLE = re.compile(
    r"INJECTION|INFUSION|VACCINE|DEPOT|\bINJ\b|AMPOULE|AMPULE|AMPUL|\bVIALS?\b|I\.V\.|\bIV\b|"
    r"IV\s+(?:FLUID|SOLUTION)|"
    r"RECONSTITUTED\s+POWDER\s+FOR\s+INJECTION|FOR\s+INJECTION",
    re.I,
)
# Leading ``IV CANNULA…`` is a supply SKU name, not ``intravenous`` formulation.
_RE_IV_CANNULA = re.compile(r"^IV\s+CANNUL", re.I)

def _mg_ml_sealed_vial(name_upper: str) -> bool:
    """True for names like ``DOPAMINE 40MG/ML 5ML`` or ``... 2MG/ML-100ML``."""
    if "MG/ML" not in name_upper:
        return False
    return bool(re.search(r"(?:^|[\s\-])(\d+)\s*ML\s*$", name_upper))
_RE_TABLET = re.compile(
    r"(TABLETS?|\bTABS\b|TAB\.|\bTAB\b|CHEWABLE\s+TABLETS?|DISPERSIBLE\s+.*TAB|"
    r"ENTERIC\s+COATED\s+.*TAB|BLISTER\s+PACK.*TABLET)",
    re.I,
)
# Non-formulation stock (still often under drug category in KEMSA sheets): keep count UOM.
_RE_SUPPLY_LIKE = re.compile(
    r"ENVELOPE|CANNULA|SYRINGE|CATHETER|FOLLEY|SUTURE|BANDAGE|GLOVES?|"
    r"AUTOCLAV|STRAPPING|COTTON\s+WOOL|GAUZE|URINE\s+BAG|PIPPETTE|TIP\s*\("
    r"|MICRO\s*CUVETTE|CUVETTES|DIAGNOSTIC\s+TESTS|RAPID\s+KIT|RAPID\s+DIAGNOSTIC|MALARIA\s+RAPID"
    r"|METHYLATED\s+SPIRIT|ETHANOL\s+DENATURED|ALCOHOL\s+CONTENT"
    r"|WATER\s+BASED\s+LUBRICANT|ZINC\s+OXIDE\s+STRAPPING",
    re.I,
)


def infer_pharmaceutical_uom(name: str) -> str:
    """Return ``product.uom`` xml id for sale/purchase UOM from free-text drug name."""
    if not name or not str(name).strip():
        return UOM_NUMBER_TABLETS
    n = str(name).strip()
    u = n.upper()

    if _RE_IV_CANNULA.match(u.strip()):
        return UOM_NUMBER_TABLETS

    if _RE_INJECTABLE.search(u):
        return UOM_SOLUTION_FOR_INJECTION
    if _mg_ml_sealed_vial(u) and "SUSPENSION" not in u and "ORAL" not in u and "NEBUL" not in u:
        if "EYE" not in u and "EAR " not in u and "GARGLE" not in u and "MOUTH WASH" not in u:
            return UOM_SOLUTION_FOR_INJECTION
    if "IMPLANT" in u and "IMPLANTATION" not in u:
        return UOM_NUMBER_TABLETS
    if "SUPPOSITORY" in u or "SUPPOSITORIES" in u:
        return UOM_SUPPOSITORY
    if "PESSARY" in u:
        return UOM_PESSARY
    if "ORAL SOLUTION" in u or "ORAL LIQUID" in u:
        return UOM_SOLUTION
    if "NEBUL" in u and "SOLUTION" in u:
        return UOM_SOLUTION
    if "SYRUP" in u:
        return UOM_SYRUP
    if "SUSPENSION" in u and "INJECTION" not in u and "FOR INJECTION" not in u:
        return UOM_ORAL_SUSPENSION
    if "EYE DROP" in u or re.search(r"\bDROPS\b", u):
        return UOM_DROPS
    if "EYE" in u and re.search(r"\bSOLUTION\b", u) and "INJECTION" not in u:
        return UOM_DROPS
    if re.search(r"\bGEL\b", u) and "GELATIN" not in u and "GELATINE" not in u:
        return UOM_CREAM
    if "CREAM" in u:
        return UOM_CREAM
    if "OINTMENT" in u:
        return UOM_OINTMENT
    if "LOTION" in u:
        return UOM_LOTION
    if "NASAL SPRAY" in u or ("SPRAY" in u and "EAR " not in u):
        return UOM_MD_INHALER
    if "INHALER" in u or "INHALATION" in u or " MDI" in u or " PUFF" in u:
        return UOM_MD_INHALER
    if re.search(r"\bSOLUTION\b", u) and "INJECTION" not in u and "FOR INJECTION" not in u:
        if "MOUTH WASH" in u or "GARGLE" in u:
            return UOM_SOLUTION
        if "EYE" in u or "EAR " in u:
            return UOM_DROPS
        return UOM_SOLUTION
    if "CHARCOAL" in u and "TABLET" not in u:
        return UOM_POWDER
    if re.search(r"\bPOWDER\b", u) and "INJECTION" not in u and "FOR INJECTION" not in u:
        return UOM_POWDER
    if "SACHET" in u or "GRANULE" in u:
        return UOM_POWDER
    if "CAPSULE" in u:
        return UOM_CAPSULE
    if re.search(r"\bCAPS\b", u):
        return UOM_CAPSULE
    if re.search(r"\bCAP\b(?!\s*TOP)", u):
        return UOM_CAPSULE
    if _RE_TABLET.search(u):
        return UOM_TABLET
    if _RE_SUPPLY_LIKE.search(u):
        return UOM_NUMBER_TABLETS
    return UOM_NUMBER_TABLETS
