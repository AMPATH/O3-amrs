# -*- coding: utf-8 -*-
"""Normalize product/drug names for duplicate detection (initializer CSVs).

Used when comparing ``drugs.csv`` (canonical) to ``kesses_*.csv`` rows so that
spelling variants like ``500MG CAP`` vs ``500MG CAPSULES`` map to the same key.
"""
from __future__ import annotations

import re
import unicodedata

_SYNONYMS: list[tuple[str, str]] = [
    (r'\bCAPSULES\b', 'CAP'),
    (r'\bCAPSULE\b', 'CAP'),
    (r'\bTABLETS\b', 'TAB'),
    (r'\bTABLET\b', 'TAB'),
    (r'\bTABS\b', 'TAB'),
    (r'\bINJECTION\b', 'INJ'),
    (r'\bINJECTIONS\b', 'INJ'),
    (r'\bSOLUTION\b', 'SOL'),
    (r'\bCREAM\b', 'CR'),
    (r'\bSUSPENSION\b', 'SUSP'),
]


def norm_basic(name: str) -> str:
    if not name:
        return ''
    s = str(name).strip().upper()
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def canonical_drug_key(name: str) -> str:
    """Stable key: drugs that differ only by TAB/TABLET/CAPSULE wording collide."""
    s = norm_basic(name)
    # "25 MG" / "25MG" → "25MG"
    s = re.sub(
        r'(\d+(?:\.\d+)?)\s*(MG|MCG|ML|IU|G)\b',
        lambda m: m.group(1) + m.group(2).upper(),
        s,
        flags=re.I,
    )
    for pat, rep in _SYNONYMS:
        s = re.sub(pat, rep, s)
    s = re.sub(r'[-–—]', ' ', s)
    s = re.sub(r'%', ' PC ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s
