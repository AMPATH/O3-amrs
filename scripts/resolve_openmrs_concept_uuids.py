#!/usr/bin/env python3
"""Deprecated entry point: resolver now targets OpenMRS **drug** UUIDs."""

from pathlib import Path
import importlib.util
import sys


def _run():
    p = Path(__file__).resolve().parent / "resolve_openmrs_drug_uuids.py"
    spec = importlib.util.spec_from_file_location("_openmrs_drug_uuids", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod.main()


if __name__ == "__main__":
    sys.stderr.write("Using resolve_openmrs_drug_uuids.py (OpenMRS **drug** uuid, not concept).\n")
    raise SystemExit(_run())
