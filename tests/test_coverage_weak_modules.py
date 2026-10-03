"""
Comprehensive tests for weak modules to raise unit test coverage >= 80%:
- src/validedi/extractors/extract_837i.py
- src/validedi/handlers/cross_segment.py
- src/validedi/handlers/claim_checks.py
- src/validedi/handlers/diagnosis_codes.py
- src/validedi/exporters/csv_exporter.py
- src/validedi/llm/prompts.py
- src/validedi/engine/batch.py
- src/backend/app/services/chat.py
- src/backend/app/services/exports.py
"""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from validedi.engine.models import Element, EnvelopeMeta, Loop, ParsedEDI, Segment, ValidationError, ValidationResult
from validedi.extractors.extract_837i import (
    _extract_claim_837i,
    _extract_diagnosis_codes,
    _extract_facility_info,
    _extract_patient_info,
    _extract_service_line_837i,
    _parse_amount,
    extract_claims_837i,
)
from validedi.handlers.cross_segment import (
    charge_total_consistency,
    charge_total_consistency_i,
    coverage_date_consistency,
    date_range_check,
    dob_vs_claim_date,
)
from validedi.handlers.claim_checks import (
    admission_type_check,
    all_zero_charges_check,
    amount_format_check,
    clm_frequency_code_check,
    diagnosis_decimal_check,
    drg_code_check,
    dtp_date_format_check,
    luhn_check_rendering,
    qualifiers_check,
)
from validedi.handlers.diagnosis_codes import (
    ICD9_PATTERN,
    ICD10_PATTERN,
    _determine_icd_version,
    validate_diagnosis_code,
)
from validedi.exporters.csv_exporter import export_claims_csv, export_errors_csv
from validedi.llm.prompts import (
    build_explanation_prompt,
    build_qa_prompt,
    extract_key_facts,
    extract_key_facts_from_loops,
)
from validedi.engine.batch import _label, batch_validate
from app.services.chat import _rule_based_fallback, ask_chat_assistant, ask_huggingface
from app.services.exports import csv_bytes, error_report_pdf_bytes, json_bytes, tsv_bytes


# ── Helpers for Building Synthetic Elements & Segments ────────────────────────


def make_elem(raw: str, components: list[str] | None = None) -> Element:
    return Element(raw=raw, components=components or [])


def make_seg(seg_id: str, *raw_values: str, position: int = 1) -> Segment:
    elements = [make_elem(v) for v in raw_values]
    return Segment(segment_id=seg_id, elements=elements, position=position)


def seg(seg_id: str, elements: list[Element], position: int = 1) -> Segment:
    return Segment(segment_id=seg_id, elements=elements, position=position)


def make_meta(transaction_type: str = "837p", sender_id: str = "SND", receiver_id: str = "RCV") -> EnvelopeMeta:
    return EnvelopeMeta(
        isa_control_number="000000001",
        gs_control_number="1",
        st_control_number="0001",
        sender_id=sender_id,
        receiver_id=receiver_id,
        interchange_date="20230101",
        interchange_time="1200",
        version="005010X222A1",
        transaction_type=transaction_type,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. extract_837i.py Tests
# ══════════════════════════════════════════════════════════════════════════════


def test_extract_837i_parse_amount():
    assert _parse_amount("") == 0.0
    assert _parse_amount(None) == 0.0
    assert _parse_amount("$1,234.56") == 1234.56
    assert _parse_amount("invalid") == 0.0


def test_extract_837i_facility_and_patient_info():
    # Loop with full facility info
    fac_loop = Loop(
        loop_id="2000A",
        segments=[
            seg("NM1", [make_elem("85"), make_elem("2"), make_elem("GENERAL HOSPITAL"), make_elem(""), make_elem(""), make_elem(""), make_elem(""), make_elem("XX"), make_elem("1234567893")]),
            seg("N3", [make_elem("100 HOSPITAL WAY")]),
            seg("N4", [make_elem("METROPOLIS"), make_elem("NY"), make_elem("10001")]),
            seg("REF", [make_elem("EI"), make_elem("123456789")]),
        ],
    )
    fac_info = _extract_facility_info(fac_loop)
    assert fac_info["name"] == "GENERAL HOSPITAL"
    assert fac_info["npi"] == "1234567893"
    assert fac_info["address"] == "100 HOSPITAL WAY"
    assert fac_info["city"] == "METROPOLIS"
    assert fac_info["state"] == "NY"
    assert fac_info["zip"] == "10001"
    assert fac_info["tax_id"] == "123456789"

    # Patient info
    pat_loop = Loop(
        loop_id="2000B",
        segments=[
            seg("NM1", [make_elem("IL"), make_elem("1"), make_elem("DOE"), make_elem("JANE"), make_elem(""), make_elem(""), make_elem(""), make_elem("MI"), make_elem("MEM12345")]),
            seg("DMG", [make_elem("D8"), make_elem("19800512"), make_elem("F")]),
            seg("N3", [make_elem("456 ELM ST")]),
            seg("N4", [make_elem("METROPOLIS"), make_elem("NY"), make_elem("10001")]),
            seg("REF", [make_elem("SY"), make_elem("987654321")]),
        ],
    )
    pat_info = _extract_patient_info(pat_loop)
    assert pat_info["last_name"] == "DOE"
    assert pat_info["first_name"] == "JANE"
    assert pat_info["member_id"] == "MEM12345"
    assert pat_info["dob"] == "19800512"
    assert pat_info["gender"] == "F"
    assert pat_info["address"] == "456 ELM ST"
    assert pat_info["ssn"] == "987654321"


def test_extract_837i_service_line_and_diagnoses():
    # Service loop with SV2 and DTP*472
    # SV2: 01=rev_code, 02=composite procedure, 03=charge, 04=unit, 05=quantity
    sv2_elem02 = Element(raw="HC:99213", components=["HC", "99213"])
    sv2_seg = seg("SV2", [make_elem("0250"), sv2_elem02, make_elem("450.00"), make_elem("UN"), make_elem("2")])
    dtp_seg = seg("DTP", [make_elem("472"), make_elem("D8"), make_elem("20230215")])
    svc_loop = Loop(loop_id="2400", segments=[sv2_seg, dtp_seg])

    svc_data = _extract_service_line_837i(svc_loop)
    assert svc_data["revenue_code"] == "0250"
    assert svc_data["procedure_code"] == "99213"
    assert svc_data["charge"] == 450.00
    assert svc_data["units"] == "2"
    assert svc_data["service_date"] == "20230215"

    # Non-composite procedure code
    sv2_raw = seg("SV2", [make_elem("0450"), make_elem("0450"), make_elem("125.50")])
    svc_raw_loop = Loop(loop_id="2400", segments=[sv2_raw])
    svc_data_raw = _extract_service_line_837i(svc_raw_loop)
    assert svc_data_raw["procedure_code"] == "0450"
    assert svc_data_raw["charge"] == 125.50

    # Missing SV2 returns None
    empty_loop = Loop(loop_id="2400", segments=[])
    assert _extract_service_line_837i(empty_loop) is None

    # Diagnosis codes extraction from HI segment
    hi_seg = seg(
        "HI",
        [
            make_elem("BK:I10"),
            make_elem("ABK:E119"),
            make_elem("APR:R079"),
            make_elem("ABN:V0001"),
            make_elem("BF:Z87891"),
        ],
    )
    diags = _extract_diagnosis_codes(hi_seg)
    assert len(diags) == 5
    assert diags[0]["type"] == "Primary"
    assert diags[0]["code"] == "I10"
    assert diags[1]["type"] == "Primary"
    assert diags[2]["type"] == "Patient Reason for Visit"
    assert diags[3]["type"] == "External Cause"
    assert diags[4]["type"] == "Additional"


def test_extract_claims_837i_full_hierarchy_multiple_claims():
    # Construct complete 2000A -> 2000B -> 2300 (multiple) with 2400 service lines
    clm05_1 = Element(raw="11:A:1", components=["11", "A", "1"])
    clm1 = seg("CLM", [make_elem("CLM-001"), make_elem("1000.00"), make_elem(""), make_elem(""), clm05_1])
    dtp1_adm = seg("DTP", [make_elem("435"), make_elem("D8"), make_elem("20230101")])
    dtp1_dis = seg("DTP", [make_elem("096"), make_elem("D8"), make_elem("20230103")])
    hi1 = seg("HI", [make_elem("BK:I10")])

    sv2_1 = seg("SV2", [make_elem("0110"), make_elem("ROOM"), make_elem("1000.00"), make_elem("UN"), make_elem("1")])
    svc_loop1 = Loop(loop_id="2400", segments=[sv2_1])
    claim_loop1 = Loop(loop_id="2300", segments=[clm1, dtp1_adm, dtp1_dis, hi1], children=[svc_loop1])

    # Second claim
    clm2 = seg("CLM", [make_elem("CLM-002"), make_elem("500.00")])
    claim_loop2 = Loop(loop_id="2300", segments=[clm2], children=[])

    subscriber_loop = Loop(loop_id="2000B", segments=[seg("NM1", [make_elem("IL"), make_elem("1"), make_elem("SMITH")])], children=[claim_loop1, claim_loop2])
    billing_loop = Loop(loop_id="2000A", segments=[seg("NM1", [make_elem("85"), make_elem("2"), make_elem("HOSPITAL A")])], children=[subscriber_loop])

    parsed = ParsedEDI(
        envelope=make_meta(transaction_type="837i"),
        segments=[],
        loops=[billing_loop],
        raw="RAW_EDI_STRING",
    )

    claims = extract_claims_837i(parsed)
    assert len(claims) == 2
    assert claims[0]["claim_id"] == "CLM-001"
    assert claims[0]["total_charge"] == 1000.00
    assert claims[0]["place_of_service"] == "11"
    assert claims[0]["bill_type"] == "A"
    assert claims[0]["claim_frequency"] == "1"
    assert claims[0]["admission_date"] == "20230101"
    assert claims[0]["discharge_date"] == "20230103"
    assert len(claims[0]["service_lines"]) == 1
    assert claims[0]["service_lines"][0]["revenue_code"] == "0110"

    assert claims[1]["claim_id"] == "CLM-002"
    assert claims[1]["total_charge"] == 500.00
    assert claims[1]["billing_provider"]["name"] == "HOSPITAL A"


# ══════════════════════════════════════════════════════════════════════════════
# 2. cross_segment.py Tests
# ══════════════════════════════════════════════════════════════════════════════


def test_cross_segment_charge_total_consistency_sv1_and_sv2():
    # Valid SV1 matching CLM02
    sv1_elem = Element(raw="100.00", components=["100.00", "UN", "1"])
    clm = seg("CLM", [make_elem("C1"), make_elem("100.00")], position=5)
    sv1 = seg("SV1", [make_elem("HC:99213"), sv1_elem], position=10)
    loop = Loop(loop_id="2300", segments=[clm], children=[Loop(loop_id="2400", segments=[sv1])])
    assert charge_total_consistency(loop) == []

    # SV1 mismatch
    clm_mismatch = seg("CLM", [make_elem("C1"), make_elem("150.00")], position=5)
    loop_mismatch = Loop(loop_id="2300", segments=[clm_mismatch], children=[Loop(loop_id="2400", segments=[sv1])])
    errs = charge_total_consistency(loop_mismatch)
    assert len(errs) == 1
    assert errs[0].code == "CHARGE_TOTAL_CHECK"

    # SV2 matching institutional CLM02
    sv2 = seg("SV2", [make_elem("0250"), make_elem("HC:99213"), make_elem("200.00")], position=12)
    clm_i = seg("CLM", [make_elem("C2"), make_elem("200.00")], position=5)
    loop_i = Loop(loop_id="2300", segments=[clm_i], children=[Loop(loop_id="2400", segments=[sv2])])
    assert charge_total_consistency(loop_i) == []
    assert charge_total_consistency_i(loop_i) == []

    # SV2 mismatch with charge_total_consistency_i
    clm_i_bad = seg("CLM", [make_elem("C2"), make_elem("300.00")], position=5)
    loop_i_bad = Loop(loop_id="2300", segments=[clm_i_bad], children=[Loop(loop_id="2400", segments=[sv2])])
    errs_i = charge_total_consistency_i(loop_i_bad)
    assert len(errs_i) == 1
    assert errs_i[0].code == "CHARGE_TOTAL_CHECK_I"

    # Missing CLM or bad charge value
    assert charge_total_consistency(Loop(loop_id="2300", segments=[])) == []
    bad_clm = seg("CLM", [make_elem("C"), make_elem("NOT_A_FLOAT")])
    assert charge_total_consistency(Loop(loop_id="2300", segments=[bad_clm])) == []
    assert charge_total_consistency_i(Loop(loop_id="2300", segments=[bad_clm])) == []


def test_cross_segment_date_range_check():
    assert date_range_check("20230101", "20230105") == []
    assert date_range_check("20230101", "20230101") == []

    errs = date_range_check("20230110", "20230101", context="(service dates)")
    assert len(errs) == 1
    assert errs[0].code == "DATE_RANGE_INVALID"

    errs_fmt = date_range_check("2023-01-10", "invalid")
    assert len(errs_fmt) == 1
    assert errs_fmt[0].code == "DATE_FORMAT_INVALID"


def test_cross_segment_dob_vs_claim_date():
    # String arguments: valid DOB before claim date
    assert dob_vs_claim_date("19900101", "20230101") == []

    # String arguments: DOB after claim date
    errs = dob_vs_claim_date("20250101", "20230101")
    assert len(errs) == 1
    assert errs[0].code == "DOB_AFTER_CLAIM"

    # String arguments: Invalid date format
    errs_fmt = dob_vs_claim_date("bad-dob", "20230101")
    assert len(errs_fmt) == 1
    assert errs_fmt[0].code == "DATE_FORMAT_INVALID"

    # Loop structure arguments: DMG and DTP
    dmg = seg("DMG", [make_elem("D8"), make_elem("20250101"), make_elem("M")])
    dtp = seg("DTP", [make_elem("472"), make_elem("D8"), make_elem("20230101")])
    loop_with_dates = Loop(loop_id="PATIENT", segments=[dmg, dtp])
    errs_loop = dob_vs_claim_date([loop_with_dates])
    assert len(errs_loop) == 1
    assert errs_loop[0].code == "DOB_AFTER_CLAIM"

    # Valid loop structure
    dmg_valid = seg("DMG", [make_elem("D8"), make_elem("19900101"), make_elem("M")])
    assert dob_vs_claim_date([Loop(loop_id="PATIENT", segments=[dmg_valid, dtp])]) == []


def test_cross_segment_coverage_date_consistency():
    dtp_start = seg("DTP", [make_elem("348"), make_elem("D8"), make_elem("20230101")])
    dtp_end = seg("DTP", [make_elem("349"), make_elem("D8"), make_elem("20231231")])
    cov_loop = Loop(loop_id="2300", segments=[dtp_start, dtp_end])
    assert coverage_date_consistency(cov_loop) == []

    # Invalid range: end before start
    dtp_end_bad = seg("DTP", [make_elem("349"), make_elem("D8"), make_elem("20221231")])
    cov_bad_loop = Loop(loop_id="2300", segments=[dtp_start, dtp_end_bad])
    errs = coverage_date_consistency(cov_bad_loop)
    assert len(errs) == 1
    assert errs[0].code == "DATE_RANGE_INVALID"


# ══════════════════════════════════════════════════════════════════════════════
# 3. claim_checks.py Tests
# ══════════════════════════════════════════════════════════════════════════════


def test_claim_checks_clm_frequency():
    # Valid frequency code '1'
    clm_valid = seg("CLM", [make_elem("C1"), make_elem("100"), make_elem(""), make_elem(""), Element(raw="11:A:1", components=["11", "A", "1"])])
    assert clm_frequency_code_check([Loop(loop_id="2300", segments=[clm_valid])]) == []

    # Invalid frequency code 'Z'
    clm_invalid = seg("CLM", [make_elem("C1"), make_elem("100"), make_elem(""), make_elem(""), Element(raw="11:A:Z", components=["11", "A", "Z"])])
    errs = clm_frequency_code_check([Loop(loop_id="2300", segments=[clm_invalid])])
    assert len(errs) == 1
    assert errs[0].code == "837-017"


def test_claim_checks_all_zero_charges():
    # Mixed charges: non-zero
    sv1_1 = seg("SV1", [make_elem("HC:99213"), make_elem("0.00")])
    sv1_2 = seg("SV1", [make_elem("HC:99214"), make_elem("100.00")])
    loop_mixed = Loop(loop_id="2300", segments=[], children=[Loop(loop_id="2400", segments=[sv1_1, sv1_2])])
    assert all_zero_charges_check([loop_mixed]) == []

    # All zero charges across SV1 and SV2
    sv2_zero = seg("SV2", [make_elem("0250"), make_elem(""), make_elem("0.00")])
    loop_zero = Loop(loop_id="2300", segments=[], children=[Loop(loop_id="2400", segments=[sv1_1, sv2_zero])])
    errs = all_zero_charges_check([loop_zero])
    assert len(errs) == 1
    assert errs[0].code == "837-018"


def test_claim_checks_admission_type_and_drg():
    # Valid admission type (1) and source (1)
    clm11_good = Element(raw="1:1", components=["1", "1"])
    clm_adm_good = seg("CLM", [make_elem("C1"), make_elem("100"), make_elem(""), make_elem(""), make_elem(""), make_elem(""), make_elem(""), make_elem(""), make_elem(""), make_elem(""), clm11_good])
    assert admission_type_check([Loop(loop_id="2300", segments=[clm_adm_good])]) == []

    # Invalid admission type '99' and source 'ZZ'
    clm11_bad = Element(raw="99:ZZ", components=["99", "ZZ"])
    clm_adm_bad = seg("CLM", [make_elem("C1"), make_elem("100"), make_elem(""), make_elem(""), make_elem(""), make_elem(""), make_elem(""), make_elem(""), make_elem(""), make_elem(""), clm11_bad])
    errs = admission_type_check([Loop(loop_id="2300", segments=[clm_adm_bad])])
    assert len(errs) == 2
    assert all(e.code == "837I-ADMISSION-TYPE" for e in errs)

    # Inpatient DRG missing check: CLM05 POS = '21' without HI*DR
    clm_inpatient = seg("CLM", [make_elem("C1"), make_elem("100"), make_elem(""), make_elem(""), Element(raw="21:A:1", components=["21", "A", "1"])])
    hi_no_drg = seg("HI", [make_elem("BK:I10")])
    errs_drg = drg_code_check([Loop(loop_id="2300", segments=[clm_inpatient, hi_no_drg])])
    assert len(errs_drg) == 1
    assert errs_drg[0].code == "837I-DRG-MISSING"

    # Inpatient with DRG
    hi_drg = seg("HI", [make_elem("DR:123")])
    assert drg_code_check([Loop(loop_id="2300", segments=[clm_inpatient, hi_drg])]) == []


def test_claim_checks_luhn_rendering_and_diagnosis_decimal():
    # Luhn rendering NPI in 2310B
    # Valid NPI: 1234567893 passes Luhn
    nm1_good = seg("NM1", [make_elem("82"), make_elem("1"), make_elem("SMITH"), make_elem(""), make_elem(""), make_elem(""), make_elem(""), make_elem("XX"), make_elem("1234567893")])
    loop_2310b_good = Loop(loop_id="2310B", segments=[nm1_good])
    assert luhn_check_rendering(loop_2310b_good) == []

    # Invalid NPI: 1234567890 fails Luhn
    nm1_bad = seg("NM1", [make_elem("82"), make_elem("1"), make_elem("SMITH"), make_elem(""), make_elem(""), make_elem(""), make_elem(""), make_elem("XX"), make_elem("1234567890")])
    loop_2310b_bad = Loop(loop_id="2310B", segments=[nm1_bad])
    errs = luhn_check_rendering(loop_2310b_bad)
    assert len(errs) == 1
    assert errs[0].code == "NPI_LUHN_2310B"

    # Decimal in diagnosis code
    hi_decimal = seg("HI", [make_elem("ABK:J18.9")])
    errs_dec = diagnosis_decimal_check([Loop(loop_id="2300", segments=[hi_decimal])])
    assert len(errs_dec) == 1
    assert errs_dec[0].code == "837-016"

    # No decimal
    hi_no_dec = seg("HI", [make_elem("ABK:J189")])
    assert diagnosis_decimal_check([Loop(loop_id="2300", segments=[hi_no_dec])]) == []


def test_claim_checks_dtp_amount_and_qualifiers():
    # DTP date format
    dtp_ok = seg("DTP", [make_elem("472"), make_elem("D8"), make_elem("20230101")])
    assert dtp_date_format_check([Loop(loop_id="2300", segments=[dtp_ok])]) == []

    dtp_bad = seg("DTP", [make_elem("472"), make_elem("D8"), make_elem("2023-01-01")])
    errs_dtp = dtp_date_format_check([Loop(loop_id="2300", segments=[dtp_bad])])
    assert len(errs_dtp) == 1
    assert errs_dtp[0].code == "DATE_FORMAT"

    # Amount format
    clm_bad_amt = seg("CLM", [make_elem("C1"), make_elem("123.456")])
    errs_amt = amount_format_check([Loop(loop_id="2300", segments=[clm_bad_amt])])
    assert len(errs_amt) == 1
    assert errs_amt[0].code == "AMOUNT_FORMAT"

    # Qualifiers check
    nm1_unusual = seg("NM1", [make_elem("85"), make_elem("2"), make_elem("HOSPITAL"), make_elem(""), make_elem(""), make_elem(""), make_elem(""), make_elem("ZZ"), make_elem("12345")])
    clm_qual = seg("CLM", [make_elem("C1"), make_elem("100"), make_elem(""), make_elem(""), make_elem("1:A:9")])
    sv1_qual = seg("SV1", [make_elem("HC:12")])
    errs_qual = qualifiers_check([Loop(loop_id="2300", segments=[nm1_unusual, clm_qual, sv1_qual])])
    assert any(e.code == "QUAL_NM108" for e in errs_qual)
    assert any(e.code == "QUAL_CLM05_FAC" for e in errs_qual)
    assert any(e.code == "QUAL_CLM05_FREQ" for e in errs_qual)
    assert any(e.code == "QUAL_SVC01" for e in errs_qual)


# ══════════════════════════════════════════════════════════════════════════════
# 4. diagnosis_codes.py Tests
# ══════════════════════════════════════════════════════════════════════════════


def test_diagnosis_codes_icd_version_determination():
    # Post 2015-10-01 should be ICD-10
    dtp_post = seg("DTP", [make_elem("472"), make_elem("D8"), make_elem("20230101")])
    loop_post = Loop(loop_id="2300", segments=[dtp_post])
    assert _determine_icd_version(loop_post) == "ICD-10"

    # Pre 2015-10-01 in service line loop (2400) should be ICD-9
    dtp_pre = seg("DTP", [make_elem("472"), make_elem("D8"), make_elem("20140501-20140502")])
    svc_loop = Loop(loop_id="2400", segments=[dtp_pre])
    loop_pre = Loop(loop_id="2300", segments=[], children=[svc_loop])
    assert _determine_icd_version(loop_pre) == "ICD-9"

    # Default with no dates should be ICD-10
    assert _determine_icd_version(Loop(loop_id="2300", segments=[])) == "ICD-10"


def test_diagnosis_codes_validation():
    # Valid ICD-10 post-2015
    hi_icd10 = seg("HI", [make_elem("ABK:I10"), make_elem("ABF:Z8700"), make_elem("ABF:M5430")])
    dtp_post = seg("DTP", [make_elem("472"), make_elem("D8"), make_elem("20200101")])
    loop_valid = Loop(loop_id="2300", segments=[hi_icd10, dtp_post])
    assert validate_diagnosis_code(loop_valid) == []

    # Invalid ICD-10 post-2015
    hi_icd10_bad = seg("HI", [make_elem("ABK:12345")])
    loop_bad_icd10 = Loop(loop_id="2300", segments=[hi_icd10_bad, dtp_post])
    errs10 = validate_diagnosis_code(loop_bad_icd10)
    assert len(errs10) == 1
    assert errs10[0].code == "DIAGNOSIS_CODE_FORMAT"

    # Valid ICD-9 pre-2015
    dtp_pre = seg("DTP", [make_elem("472"), make_elem("D8"), make_elem("20120101")])
    hi_icd9 = seg("HI", [make_elem("BK:25000"), make_elem("BF:8842"), make_elem("BF:V700")])
    loop_valid_icd9 = Loop(loop_id="2300", segments=[hi_icd9, dtp_pre])
    assert validate_diagnosis_code(loop_valid_icd9) == []

    # Invalid ICD-9 pre-2015
    hi_icd9_bad = seg("HI", [make_elem("BK:ZZZ")])
    loop_bad_icd9 = Loop(loop_id="2300", segments=[hi_icd9_bad, dtp_pre])
    errs9 = validate_diagnosis_code(loop_bad_icd9)
    assert len(errs9) == 1
    assert errs9[0].code == "DIAGNOSIS_CODE_FORMAT"

    # Missing HI segment
    assert validate_diagnosis_code(Loop(loop_id="2300", segments=[])) == []


# ══════════════════════════════════════════════════════════════════════════════
# 5. csv_exporter.py Tests
# ══════════════════════════════════════════════════════════════════════════════


def test_csv_exporter_errors_and_claims(tmp_path: Path):
    dummy_parsed = ParsedEDI(
        envelope=make_meta(transaction_type="837p"),
        segments=[],
        loops=[],
        raw="RAW",
    )
    vr = ValidationResult(
        parsed=dummy_parsed,
        errors=[
            ValidationError(
                code="TEST_ERR",
                severity="error",
                segment="CLM",
                element="CLM02",
                loop="2300",
                position=5,
                message="Sample error message",
            )
        ],
    )

    # Export errors to string
    csv_str = export_errors_csv(vr)
    assert "TEST_ERR" in csv_str
    assert "Sample error message" in csv_str

    # Export errors to file
    err_file = str(tmp_path / "errors.csv")
    ret = export_errors_csv(vr, filepath=err_file)
    assert ret == ""
    assert Path(err_file).read_text(encoding="utf-8").startswith("severity,code")

    # Export claims from ParsedEDI
    clm_seg = seg("CLM", [make_elem("CLM100"), make_elem("500.00"), make_elem(""), make_elem(""), Element(raw="11:A:1", components=["11", "A", "1"])])
    sv1_seg = seg("SV1", [make_elem("HC:99213"), Element(raw="500.00", components=["500.00"])])
    parsed_837p = ParsedEDI(
        envelope=make_meta(transaction_type="837p"),
        segments=[],
        loops=[
            Loop(
                loop_id="2000A",
                segments=[seg("NM1", [make_elem("85"), make_elem("2"), make_elem("CLINIC"), make_elem(""), make_elem(""), make_elem(""), make_elem(""), make_elem("XX"), make_elem("1234567893")])],
                children=[
                    Loop(
                        loop_id="2000B",
                        segments=[seg("NM1", [make_elem("IL"), make_elem("1"), make_elem("SMITH"), make_elem("JOHN")])],
                        children=[
                            Loop(loop_id="2300", segments=[clm_seg], children=[Loop(loop_id="2400", segments=[sv1_seg])])
                        ],
                    )
                ],
            )
        ],
        raw="RAW_837P",
    )

    claims_csv = export_claims_csv(parsed_837p)
    assert "CLM100" in claims_csv
    assert "99213" in claims_csv

    # Claims export to file
    claim_file = str(tmp_path / "claims.csv")
    export_claims_csv(parsed_837p, filepath=claim_file)
    assert "CLM100" in Path(claim_file).read_text(encoding="utf-8")

    # Non-837 transaction returns header only
    parsed_835 = ParsedEDI(
        envelope=make_meta(transaction_type="835"),
        segments=[],
        loops=[],
        raw="RAW_835",
    )
    non_837_csv = export_claims_csv(parsed_835)
    assert non_837_csv.strip() == "claim_id,patient_name,provider_npi,service_date,total_charge,place_of_service,diagnosis_codes,procedure_code,procedure_charge"


# ══════════════════════════════════════════════════════════════════════════════
# 6. prompts.py Tests
# ══════════════════════════════════════════════════════════════════════════════


def test_prompts_builders_and_extract_key_facts():
    parsed = ParsedEDI(
        envelope=make_meta(transaction_type="837p", sender_id="SUBMITTER1", receiver_id="PAYER1"),
        segments=[],
        loops=[
            Loop(
                loop_id="2300",
                segments=[seg("CLM", [make_elem("CLM01"), make_elem("250.00")])],
                children=[],
            )
        ],
        raw="RAW_837P",
    )
    val = ValidationResult(
        parsed=parsed,
        errors=[ValidationError(code="ERR01", severity="error", segment="CLM", position=1, message="Invalid charge")],
    )

    # Explanation prompt with business data
    prompt = build_explanation_prompt(parsed, val, extracted_data={"claim_id": "CLM01"})
    assert "TRANSACTION TYPE: 837p" in prompt
    assert "SUBMITTER1" in prompt
    assert "ERR01" in prompt
    assert "EXTRACTED BUSINESS DATA" in prompt

    # QA prompt
    qa_prompt = build_qa_prompt("Why was the claim rejected?", parsed, val)
    assert "Why was the claim rejected?" in qa_prompt
    assert "ERR01" in qa_prompt

    # extract_key_facts_from_loops for 835 and 834
    bpr = seg("BPR", [make_elem("I"), make_elem("1500.50"), make_elem("C"), make_elem("ACH"), make_elem("CCP"), make_elem("01"), make_elem("123"), make_elem("DA"), make_elem("456"), make_elem("123456789"), make_elem(""), make_elem("01"), make_elem("987"), make_elem("DA"), make_elem("654"), make_elem("20230301")])
    facts_835 = extract_key_facts_from_loops("835", [Loop(loop_id="BPR_LOOP", segments=[bpr])])
    assert "$1,500.50" in facts_835
    assert "20230301" in facts_835

    facts_834 = extract_key_facts_from_loops("834", [Loop(loop_id="2000", segments=[]), Loop(loop_id="2000", segments=[])])
    assert "Total Members: 2" in facts_834

    # extract_key_facts deprecated dictionary handler
    dict_837 = {
        "transaction_purpose": {"purpose": "Original", "transaction_type": "837P", "date": "20230101"},
        "submitter": {"name": "SUB1", "id": "ID1"},
        "billing_provider": {"name": "PROV1", "id": "1234567893"},
        "claims": [{"claim_id": "C1", "total_charge": "$500.00", "diagnosis_codes": [{"code": "I10"}]}],
    }
    facts_dict_837 = extract_key_facts("837P", dict_837)
    assert "PROV1" in facts_dict_837
    assert "$500.00" in facts_dict_837

    dict_835 = {
        "financial_info": {"total_payment_amount": "$1000", "payment_method": "ACH", "check_eft_date": "20230101"},
        "payer": {"name": "PAYER A"},
        "claim_payments": [{"claim_id": "C1"}],
    }
    assert "PAYER A" in extract_key_facts("835", dict_835)

    dict_834 = {
        "transaction_purpose": "2",
        "effective_date": "20230101",
        "sponsor": {"name": "SPONSOR INC"},
        "members": [{"id": "M1"}],
    }
    assert "SPONSOR INC" in extract_key_facts("834", dict_834)


# ══════════════════════════════════════════════════════════════════════════════
# 7. batch.py Tests
# ══════════════════════════════════════════════════════════════════════════════


def test_batch_validate(tmp_path: Path):
    assert batch_validate([]) == []

    # Prepare temporary files
    sample_835_text = (
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *230101*1200*^*00501*000000001*0*P*:~\n"
        "GS*HP*SENDER*RECEIVER*20230101*1200*1*X*005010X221A1~\n"
        "ST*835*0001*005010X221A1~\n"
        "BPR*I*150.00*C*ACH*CCP*01*123456789*DA*987654321*1234567890*01*999999999*DA*111111111*20230101~\n"
        "TRN*1*12345*1234567890~\n"
        "SE*5*0001~GE*1*1~IEA*1*000000001~"
    )
    f1 = tmp_path / "valid.edi"
    f1.write_text(sample_835_text)

    # Batch validation with Path and raw string
    results = batch_validate([f1, sample_835_text, "MALFORMED_GARBAGE_NO_ENVELOPE"])
    assert len(results) == 3
    assert results[0]["source"] == "valid.edi"
    assert results[0]["result"] is not None
    assert results[1]["result"] is not None
    assert results[2]["error"] is not None or (results[2]["result"] is not None and not results[2]["result"].is_valid)

    # Test _label helper
    assert _label(Path("foo/bar.edi")) == "bar.edi"
    assert _label("foo/baz.edi") == "baz.edi"
    assert _label("X" * 50).endswith("…")

    # fail_fast=True with a malformed input raises exception
    with pytest.raises(Exception):
        batch_validate(["NON_EXISTENT_FILE_THAT_FAILS_FAST.EDI"], fail_fast=True)


# ══════════════════════════════════════════════════════════════════════════════
# 8. backend app/services/chat.py Tests
# ══════════════════════════════════════════════════════════════════════════════


def test_chat_service_rule_based_fallback():
    ctx = {
        "transaction_type": "837P",
        "errors": [{"code": "CLM_ERR", "message": "Missing segment", "segment": "CLM"}],
        "valid": False,
        "sender_id": "CLINIC1",
        "receiver_id": "PAYER1",
    }

    assert "837P" in _rule_based_fallback("What is this transaction type?", ctx)
    assert "validation issues" in _rule_based_fallback("Show me any errors", ctx)
    assert "CLINIC1" in _rule_based_fallback("Who are the trading partners and sender?", ctx)
    assert "Overview of 837P" in _rule_based_fallback("Give me a summary", ctx)
    assert "EDI Assistant Response" in _rule_based_fallback("Help with generic query", ctx)

    # Clean context without errors
    clean_ctx = {"transaction_type": "835", "errors": [], "valid": True}
    assert "passed validation with 0 fatal errors" in _rule_based_fallback("Are there any errors?", clean_ctx)


@pytest.mark.anyio
async def test_chat_service_providers():
    ctx = {"transaction_type": "837P", "errors": []}

    # 1. Groq mock response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Groq mock response answer."}}]
    }

    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_key_123"}), patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)):
        ans = await ask_chat_assistant("What is this?", ctx)
        assert ans == "Groq mock response answer."

    # 2. Hugging Face mock response
    mock_hf_resp = MagicMock()
    mock_hf_resp.status_code = 200
    mock_hf_resp.json.return_value = [{"generated_text": "HuggingFace response answer."}]

    with patch.dict(os.environ, {"GROQ_API_KEY": "", "HUGGINGFACE_API_KEY": "hf_test_token"}), patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_hf_resp)):
        ans_hf = await ask_chat_assistant("What is this?", ctx)
        assert ans_hf == "HuggingFace response answer."

    # 3. Fallback when network error occurs
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_key"}), patch("httpx.AsyncClient.post", AsyncMock(side_effect=Exception("Network error"))):
        ans_fb = await ask_chat_assistant("What is the type?", ctx)
        assert "837P" in ans_fb

    # 4. Backward compatibility alias
    assert ask_huggingface == ask_chat_assistant


# ══════════════════════════════════════════════════════════════════════════════
# 9. backend app/services/exports.py Tests
# ══════════════════════════════════════════════════════════════════════════════


def test_exports_service():
    # json_bytes
    j_bytes = json_bytes({"status": "ok", "count": 5})
    assert b'"status": "ok"' in j_bytes

    # csv_bytes empty
    assert csv_bytes([]) == b""

    # csv_bytes with totals
    rows = [
        {"claim_id": "CLM1", "charge": 100.0, "status": "PAID"},
        {"claim_id": "CLM2", "charge": 250.50, "status": "PENDING"},
    ]
    c_bytes = csv_bytes(rows, include_totals=True)
    c_str = c_bytes.decode("utf-8")
    assert c_str.startswith("\ufeff")  # BOM
    assert "CLM1" in c_str
    assert "TOTAL" in c_str
    assert "350.5" in c_str

    # tsv_bytes
    assert tsv_bytes([]) == b""
    t_bytes = tsv_bytes(rows)
    t_str = t_bytes.decode("utf-8")
    assert "\t" in t_str
    assert "CLM1\t100.0\tPAID" in t_str

    # error_report_pdf_bytes
    issues = [
        {"severity": "error", "code": "ERR01", "segment_id": "CLM", "message": "Missing CLM02 charge"},
        {"severity": "warning", "code": "WARN01", "segment_id": "SV1", "message": "High amount"},
    ]
    pdf = error_report_pdf_bytes(issues)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 200

    # Multi-page PDF test (> 60 issues to trigger page break)
    many_issues = [
        {"severity": "error", "code": f"E{i}", "segment_id": "SEG", "message": f"Test message {i}"}
        for i in range(70)
    ]
    pdf_multi = error_report_pdf_bytes(many_issues)
    assert len(pdf_multi) > len(pdf)


# ══════════════════════════════════════════════════════════════════════════════
# 10. extract_835.py & extract_834.py & app.adapters Tests
# ══════════════════════════════════════════════════════════════════════════════


def test_extract_835_full_hierarchy():
    from validedi.extractors.extract_835 import extract_payments_835

    bpr_seg = seg("BPR", [make_elem("I"), make_elem("1500.00"), make_elem("C"), make_elem("ACH"), make_elem("CCP"), make_elem("01"), make_elem("ACT123"), make_elem("DA"), make_elem("ACT456"), make_elem("999999999"), make_elem(""), make_elem("01"), make_elem("888888888"), make_elem("DA"), make_elem("777777777"), make_elem("20230501")])
    payer_loop = Loop(loop_id="1000A", segments=[
        seg("NM1", [make_elem("PR"), make_elem("2"), make_elem("BIG PAYER"), make_elem(""), make_elem(""), make_elem(""), make_elem(""), make_elem("XX"), make_elem("1234567893")]),
        seg("N3", [make_elem("100 PAYER BLVD")]),
        seg("N4", [make_elem("NEW YORK"), make_elem("NY"), make_elem("10001")]),
        seg("PER", [make_elem("CX"), make_elem("SUPPORT"), make_elem("TE"), make_elem("8005551212")]),
        seg("REF", [make_elem("EI"), make_elem("123456789")]),
    ])
    payee_loop = Loop(loop_id="1000B", segments=[
        seg("NM1", [make_elem("PE"), make_elem("2"), make_elem("COMMUNITY CLINIC"), make_elem(""), make_elem(""), make_elem(""), make_elem(""), make_elem("XX"), make_elem("9876543210")]),
    ])

    clp_seg = seg("CLP", [make_elem("CLM-001"), make_elem("1"), make_elem("500.00"), make_elem("450.00"), make_elem("50.00"), make_elem("12"), make_elem("ICN123456")])
    nm1_qc = seg("NM1", [make_elem("QC"), make_elem("1"), make_elem("SMITH"), make_elem("JOHN")])
    cas_seg = seg("CAS", [make_elem("CO"), make_elem("45"), make_elem("50.00")])
    svc_elem = Element(raw="HC:99213", components=["HC", "99213"])
    svc_seg = seg("SVC", [svc_elem, make_elem("500.00"), make_elem("450.00"), make_elem(""), make_elem("1")])
    svc_loop = Loop(loop_id="2110", segments=[svc_seg, cas_seg])
    claim_loop = Loop(loop_id="2100", segments=[clp_seg, nm1_qc], children=[svc_loop])
    prov_loop = Loop(loop_id="2000", segments=[], children=[claim_loop])

    parsed_835 = ParsedEDI(
        envelope=make_meta(transaction_type="835"),
        segments=[],
        loops=[Loop(loop_id="ROOT", segments=[bpr_seg]), payer_loop, payee_loop, prov_loop],
        raw="RAW_835",
    )

    data = extract_payments_835(parsed_835)
    assert data["transaction_type"] == "835"
    assert data["payment_summary"]["total_amount"] == 1500.00
    assert data["payment_summary"]["payment_method"] == "ACH"
    assert data["payer"]["name"] == "BIG PAYER"
    assert data["payer"]["contact"]["phone"] == "8005551212"
    assert data["payee"]["name"] == "COMMUNITY CLINIC"
    assert len(data["claims"]) == 1
    assert data["claims"][0]["patient_account"] == "CLM-001"
    assert data["claims"][0]["total_charged"] == 500.00
    assert data["claims"][0]["total_paid"] == 450.00
    assert len(data["claims"][0]["services"]) == 1
    assert data["claims"][0]["services"][0]["procedure_code"] == "99213"
    assert len(data["claims"][0]["services"][0]["adjustments"]) == 1


def test_extract_834_full_hierarchy():
    from validedi.extractors.extract_834 import extract_enrollments_834

    bgn_seg = seg("BGN", [make_elem("00"), make_elem("12345"), make_elem("20230101"), make_elem("1200"), make_elem(""), make_elem(""), make_elem(""), make_elem("2")])
    sponsor_loop = Loop(loop_id="1000A", segments=[
        seg("N1", [make_elem("P5"), make_elem("ACME CORP"), make_elem("FI"), make_elem("123456789")]),
    ])
    insurer_loop = Loop(loop_id="1000B", segments=[
        seg("N1", [make_elem("IN"), make_elem("HEALTH INSURER"), make_elem("XV"), make_elem("987654321")]),
    ])

    ins_seg = seg("INS", [make_elem("Y"), make_elem("18"), make_elem("030"), make_elem("XN"), make_elem("A")])
    ref_seg = seg("REF", [make_elem("0F"), make_elem("MEMB999")])
    nm1_seg = seg("NM1", [make_elem("IL"), make_elem("1"), make_elem("DOE"), make_elem("JANE")])
    dmg_seg = seg("DMG", [make_elem("D8"), make_elem("19850101"), make_elem("F")])
    hd_seg = seg("HD", [make_elem("030"), make_elem(""), make_elem("HLT")])
    dtp_seg = seg("DTP", [make_elem("348"), make_elem("D8"), make_elem("20230101")])
    cov_loop = Loop(loop_id="2300", segments=[hd_seg, dtp_seg])
    member_loop = Loop(loop_id="2000", segments=[ins_seg, ref_seg, nm1_seg, dmg_seg], children=[cov_loop])

    parsed_834 = ParsedEDI(
        envelope=make_meta(transaction_type="834"),
        segments=[],
        loops=[Loop(loop_id="ROOT", segments=[bgn_seg]), sponsor_loop, insurer_loop, member_loop],
        raw="RAW_834",
    )

    data = extract_enrollments_834(parsed_834)
    assert data["transaction_type"] == "834"
    assert data["sponsor"]["name"] == "ACME CORP"
    assert data["insurer"]["name"] == "HEALTH INSURER"
    assert len(data["members"]) == 1
    assert data["members"][0]["subscriber_number"] == "MEMB999"
    assert data["members"][0]["demographics"]["last_name"] == "DOE"
    assert data["members"][0]["coverage"]["insurance_line_code"] == "HLT"


def test_adapters_edge_cases():
    from app.adapters import validedi_error_to_issue, extract_claim_amounts_for_837, to_segment_text
    from app.models import Segment as AppSegment

    # Test error mapping with warning
    warn_err = ValidationError(
        code="CNT-001",
        severity="warning",
        segment="SE",
        element="SE01",
        loop="2300",
        position=5,
        message="Count error",
    )
    issue = validedi_error_to_issue(warn_err)
    assert issue.code == "SE_COUNT_MISMATCH"
    assert issue.severity == "warning"
    assert issue.element_position == 1

    # Test unknown code fallback
    unk_err = ValidationError(
        code="XYZ-UNKNOWN",
        severity="error",
        segment="CLM",
        position=1,
        message="Unknown issue",
    )
    unk_issue = validedi_error_to_issue(unk_err)
    assert unk_issue.code == "XYZ-UNKNOWN"

    # Test extract_claim_amounts_for_837
    segs = [
        AppSegment(id="CLM", elements=["CLM1", "500.00"], line_number=1),
        AppSegment(id="SV1", elements=["HC:99213", "250.00"], line_number=2),
        AppSegment(id="SV2", elements=["0250", "250.00"], line_number=3),
    ]
    clm_tot, svc_tot = extract_claim_amounts_for_837(segs)
    assert clm_tot == 500.0
    assert svc_tot == 500.0

    # Malformed / empty elements
    segs2 = [
        AppSegment(id="CLM", elements=[], line_number=1),
        AppSegment(id="CLM", elements=["CLM2", "not_a_number"], line_number=2),
        AppSegment(id="SV1", elements=["HC:99213"], line_number=3),
        AppSegment(id="SV1", elements=["HC:99213", "bad_num"], line_number=4),
        AppSegment(id="SV2", elements=[], line_number=5),
        AppSegment(id="SV2", elements=["0250", "invalid"], line_number=6),
    ]
    clm_tot2, svc_tot2 = extract_claim_amounts_for_837(segs2)
    assert clm_tot2 == 0.0
    assert svc_tot2 == 0.0


def test_llm_explainer_offline_and_mock():
    from validedi.llm.explainer import LLMExplainer, ExplainResult, explain

    res_mock = ParsedEDI(
        envelope=make_meta(transaction_type="837P"),
        segments=[seg("CLM", [make_elem("1"), make_elem("100.00")])],
        loops=[],
        raw="CLM*1*100.00~",
    )
    val_mock = ValidationResult(valid=True, errors=[], warnings=[], transaction_type="837P", parsed=res_mock)

    # Offline / Rule-based
    explainer = LLMExplainer()
    res = explainer.explain(res_mock, val_mock)
    assert isinstance(res, ExplainResult)
    assert res.source == "rule_based"
    assert "837P" in str(res)

    # Q&A without LLM
    ans = explainer.ask_followup("What is this?", res_mock, val_mock)
    assert "No LLM provided" in ans

    # With Mock LLM
    mock_llm = lambda prompt: f"Analysis of prompt with len {len(prompt)}"
    explainer_with_llm = LLMExplainer(llm=mock_llm)
    res_llm = explainer_with_llm.explain(res_mock, val_mock)
    assert res_llm.source == "llm"
    assert "Analysis of prompt" in res_llm.report

    # Ask followup with Mock LLM
    ans_llm = explainer_with_llm.ask_followup("Is this valid?", res_mock, val_mock)
    assert "Analysis of prompt" in ans_llm

    # Error handling in LLM fallback
    failing_llm = lambda prompt: (_ for _ in ()).throw(RuntimeError("API down"))
    explainer_fail = LLMExplainer(llm=failing_llm)
    res_fail = explainer_fail.explain(res_mock, val_mock)
    assert res_fail.source == "rule_based"
    assert "API down" in res_fail.metadata["error"]

    ans_fail = explainer_fail.ask_followup("test", res_mock, val_mock)
    assert "Error calling LLM" in ans_fail

    # Convenience function
    conv_res = explain(res_mock, val_mock, force_rule_based=True)
    assert conv_res.source == "rule_based"


def test_llm_delete_custom_config(tmp_path):
    import yaml
    from validedi.llm.delete import delete_custom_config
    from validedi.llm._exceptions import RuleNotFoundError

    config_dir = tmp_path / "config"
    rules_dir = config_dir / "rules"
    rules_dir.mkdir(parents=True)

    dummy_rules_file = rules_dir / "custom.yaml"
    dummy_rules_file.write_text(
        yaml.dump({
            "version": "1.0",
            "rules": [
                {"id": "CUSTOM-001", "name": "Custom 1", "description": "desc 1"},
                {"id": "CUSTOM-002", "name": "Custom 2", "description": "desc 2"},
            ]
        }),
        encoding="utf-8"
    )

    # Dry run
    res_dry = delete_custom_config("CUSTOM-001", config_dir=config_dir, dry_run=True)
    assert res_dry.success is True
    assert res_dry.rule_id == "CUSTOM-001"
    # Verify file was not changed
    content = yaml.safe_load(dummy_rules_file.read_text(encoding="utf-8"))
    assert len(content["rules"]) == 2

    # Actual delete
    res_del = delete_custom_config("CUSTOM-001", config_dir=config_dir, create_backups=True)
    assert res_del.success is True
    content_after = yaml.safe_load(dummy_rules_file.read_text(encoding="utf-8"))
    assert len(content_after["rules"]) == 1
    assert content_after["rules"][0]["id"] == "CUSTOM-002"

    # Rule not found
    try:
        delete_custom_config("NON_EXISTENT", config_dir=config_dir)
        assert False, "Should have raised RuleNotFoundError"
    except RuleNotFoundError:
        pass


def test_json_exporter_full(tmp_path):
    from validedi.exporters.json_exporter import export_json, export_json_to_file

    parsed = ParsedEDI(
        envelope=make_meta(transaction_type="837p"),
        segments=[seg("CLM", [make_elem("CLM01"), make_elem("100.00")])],
        loops=[],
        raw="CLM*CLM01*100.00~",
    )
    val = ValidationResult(
        valid=True,
        errors=[ValidationError(code="TEST", severity="error", segment="CLM", position=1, message="err")],
        warnings=[],
        transaction_type="837p",
        parsed=parsed,
    )

    data = export_json(parsed, validation_result=val, include_raw=True)
    assert data["transaction_type"] == "837p"
    assert data["envelope"]["sender_id"] == "SND"
    assert data["validation"]["is_valid"] is False
    assert len(data["validation"]["errors"]) == 1
    assert data["raw_edi"] == "CLM*CLM01*100.00~"

    # Test file export
    out_file = tmp_path / "export.json"
    export_json_to_file(parsed, str(out_file), validation_result=val, include_raw=True)
    assert out_file.exists()
    assert "CLM01" in out_file.read_text(encoding="utf-8")



