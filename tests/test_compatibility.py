"""
Compatibility test comparing legacy app.validation.rules with validedi validation.
"""
from __future__ import annotations

from pathlib import Path
import pytest

from app.parser.x12_parser import parse_x12
from app.validation.rules import validate as old_validate
from app.adapters import parse_edi_content, validate_edi_content
from test_api_endpoints import SAMPLE_834, SAMPLE_835, SAMPLE_837P


def test_compatibility_samples() -> None:
    sample_files = {
        "sample_837p.edi": Path("sample_837p.edi").read_text(encoding="utf-8"),
        "sample_835.edi": Path("sample_835.edi").read_text(encoding="utf-8"),
        "SAMPLE_837P": SAMPLE_837P,
        "SAMPLE_835": SAMPLE_835,
        "SAMPLE_834": SAMPLE_834,
    }

    print("\n" + "=" * 60)
    print("COMPATIBILITY COMPARISON REPORT: Legacy vs Validedi")
    print("=" * 60)

    for name, content in sample_files.items():
        p_old = parse_x12(content)
        v_old = old_validate(p_old)
        old_codes = sorted({i.code for i in v_old.issues})

        v_new = validate_edi_content(content)
        new_codes = sorted({i.code for i in v_new.issues})

        print(f"\n[{name}]")
        print(f"  Legacy:  valid={v_old.valid}, issues={len(v_old.issues)}, codes={old_codes}")
        print(f"  Validedi: valid={v_new.valid}, issues={len(v_new.issues)}, codes={new_codes}")

        diff_only_in_old = set(old_codes) - set(new_codes)
        diff_only_in_new = set(new_codes) - set(old_codes)
        if diff_only_in_old:
            print(f"  Only in Legacy: {diff_only_in_old}")
        if diff_only_in_new:
            print(f"  Only in Validedi: {diff_only_in_new}")

    print("=" * 60 + "\n")
