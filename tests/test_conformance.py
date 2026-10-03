"""
Conformance test suite validating synthetic files in tests/fixtures/conformance/.
Asserts that each invalid fixture triggers the exact expected rule code,
and each valid fixture does not trigger that rule code.
"""

from pathlib import Path

import pytest

from validedi.engine.parser import parse
from validedi.engine.validator import validate

CONFORMANCE_DIR = Path(__file__).parent / "fixtures" / "conformance"

RULE_CASES = [
    ("ge_count_mismatch", "GE_COUNT_MISMATCH"),
    ("iea_count_mismatch", "IEA_COUNT_MISMATCH"),
    ("835_007", "835-007"),
    ("hl_hierarchy_invalid", "HL_HIERARCHY_INVALID"),
    ("clm_sum_mismatch", "CLM_SUM_MISMATCH"),
    ("format_isa09_date", "FORMAT_ISA09_DATE"),
    ("format_isa10_time", "FORMAT_ISA10_TIME"),
    ("format_gs04_date", "FORMAT_GS04_DATE"),
    ("dtp_range_invalid", "DTP_RANGE_INVALID"),
    ("coverage_date_consistency", "COVERAGE_DATE_CONSISTENCY"),
    ("member_duplicate", "MEMBER_DUPLICATE"),
    ("se_count_mismatch", "SE_COUNT_MISMATCH"),
]


@pytest.mark.parametrize("rule_name,expected_code", RULE_CASES)
def test_conformance_invalid_file_triggers_exact_code(rule_name: str, expected_code: str):
    """Verify invalid fixture triggers the exact rule code."""
    file_path = CONFORMANCE_DIR / f"{rule_name}_invalid.edi"
    assert file_path.exists(), f"Fixture missing: {file_path}"
    
    parsed = parse(file_path)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert expected_code in codes, f"Expected {expected_code} to fire on {file_path.name}, got {codes}"


@pytest.mark.parametrize("rule_name,expected_code", RULE_CASES)
def test_conformance_valid_file_passes_rule(rule_name: str, expected_code: str):
    """Verify valid fixture does not trigger the rule code."""
    file_path = CONFORMANCE_DIR / f"{rule_name}_valid.edi"
    assert file_path.exists(), f"Fixture missing: {file_path}"
    
    parsed = parse(file_path)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert expected_code not in codes, f"Expected {expected_code} not to fire on {file_path.name}, but it fired in {codes}"
