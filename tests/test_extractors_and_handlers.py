"""
Unit tests for data extractors, rule handlers, and exporters in validedi.
"""
from __future__ import annotations

import pytest
from validedi import parse
from validedi.extractors import (
    extract_claims,
    extract_enrollments,
    extract_payments,
)
from validedi.exporters.json_exporter import export_json, export_json_to_file
from validedi.handlers.claim_checks import clm_frequency_code_check
from validedi.handlers.cross_segment import charge_total_consistency
from validedi.handlers.diagnosis_codes import validate_diagnosis_code
from validedi.handlers.duplicate_check import duplicate_member_check

SAMPLE_837P_TEXT = (
    "ISA*00*          *00*          *ZZ*SUBMITTER1     *ZZ*RECEIVER1      *260824*1030*U*00501*000000001*0*P*>~\n"
    "GS*HC*SUBMITTER1*RECEIVER1*20260824*1030*1*X*005010X222A1~\n"
    "ST*837*0001*005010X222A1~\n"
    "BHT*0019*00*244579*20260824*1030*CH~\n"
    "NM1*41*2*PREMIUM HEALTH INC*****46*1234567890~\n"
    "PER*IC*EDI DEPT*TE*8005551212~\n"
    "NM1*40*2*HEALTHPAY INC*****46*9876543210~\n"
    "HL*1**20*1~\n"
    "PRV*BI*PXC*207Q00000X~\n"
    "NM1*85*2*METRO MEDICAL CENTER*****XX*1992837465~\n"
    "N3*100 MAIN STREET~\n"
    "N4*METROPOLIS*NY*10001~\n"
    "REF*EI*123456789~\n"
    "HL*2*1*22*0~\n"
    "SBR*P*18*GRP12345******CI~\n"
    "NM1*IL*1*SMITH*JOHN*M***MI*SUB12345678~\n"
    "N3*456 ELM AVE~\n"
    "N4*METROPOLIS*NY*10001~\n"
    "DMG*D8*19800512*M~\n"
    "NM1*PR*2*HEALTHPAY INC*****PI*98765~\n"
    "CLM*CLM-99401*1250.00***11:B:1*Y*A*Y*Y~\n"
    "HI*BK:99214*BF:78009~\n"
    "LX*1~\n"
    "SV1*HC:99214*1250.00*UN*1***1~\n"
    "DTP*472*D8*20260820~\n"
    "SE*25*0001~\n"
    "GE*1*1~\n"
    "IEA*1*000000001~"
)

SAMPLE_835_TEXT = (
    "ISA*00*          *00*          *ZZ*PAYER1         *ZZ*PROVIDER1      *260824*1100*U*00501*000000002*0*P*>~\n"
    "GS*HP*PAYER1*PROVIDER1*20260824*1100*2*X*005010X221A1~\n"
    "ST*835*0002~\n"
    "BPR*I*1250.00*C*ACH*CTX*01*999999999*DA*111111*1999999999**01*999999999*DA*222222*20260824~\n"
    "TRN*1*123456789*1999999999~\n"
    "N1*PR*PAYER ONE~\n"
    "N1*PE*METRO MEDICAL CENTER*XX*1992837465~\n"
    "CLP*CLM-99401*1*1250.00*1000.00*250.00*MC*12345678901*11:B:1*1~\n"
    "CAS*CO*45*250.00~\n"
    "SVC*HC:99214*1250.00*1000.00~\n"
    "DTM*472*20260820~\n"
    "SE*10*0002~\n"
    "GE*1*2~\n"
    "IEA*1*000000002~"
)

SAMPLE_834_TEXT = (
    "ISA*00*          *00*          *ZZ*SPONSOR1       *ZZ*PAYER1         *260824*1200*U*00501*000000003*0*P*>~\n"
    "GS*BE*SPONSOR1*PAYER1*20260824*1200*3*X*005010X220A1~\n"
    "ST*834*0003~\n"
    "BGN*00*12345*20260824*1200****2~\n"
    "N1*P5*SPONSOR COMPANY~\n"
    "INS*Y*18*001*28*A***FT~\n"
    "REF*0F*MEMB1001~\n"
    "NM1*IL*1*DOE*JANE*A***34*123456789~\n"
    "HD*030**IND~\n"
    "DTP*348*D8*20260101~\n"
    "SE*9*0003~\n"
    "GE*1*3~\n"
    "IEA*1*000000003~"
)


def test_extract_claims_837p() -> None:
    parsed = parse(SAMPLE_837P_TEXT)
    claims = extract_claims(parsed)
    assert isinstance(claims, list)
    assert len(claims) >= 1
    c = claims[0]
    assert c["claim_id"] == "CLM-99401"
    assert c["total_charge"] == 1250.00


def test_extract_payments_835() -> None:
    parsed = parse(SAMPLE_835_TEXT)
    payments = extract_payments(parsed)
    assert payments["transaction_type"] == "835"
    assert payments["payment_summary"].get("total_amount") == 1250.00


def test_extract_enrollments_834() -> None:
    parsed = parse(SAMPLE_834_TEXT)
    enrollments = extract_enrollments(parsed)
    assert enrollments["transaction_type"] == "834"
    assert len(enrollments["members"]) >= 1
    m = enrollments["members"][0]
    assert "demographics" in m


def test_extractor_type_mismatch_raises() -> None:
    p835 = parse(SAMPLE_835_TEXT)
    with pytest.raises(ValueError):
        extract_claims(p835)

    p837 = parse(SAMPLE_837P_TEXT)
    with pytest.raises(ValueError):
        extract_payments(p837)

    with pytest.raises(ValueError):
        extract_enrollments(p837)


def test_export_to_json(tmp_path) -> None:
    parsed = parse(SAMPLE_837P_TEXT)
    json_data = export_json(parsed)
    assert json_data["transaction_type"] == "837p"

    out_file = tmp_path / "out.json"
    export_json_to_file(parsed, str(out_file))
    assert out_file.exists()
    assert out_file.stat().st_size > 0


def test_clm_handlers() -> None:
    parsed = parse(SAMPLE_837P_TEXT)
    errors = clm_frequency_code_check(parsed.loops)
    assert isinstance(errors, list)
    if parsed.loops:
        c_errors = charge_total_consistency(parsed.loops[0])
        assert isinstance(c_errors, list)
        d_errors = validate_diagnosis_code(parsed.loops[0])
        assert isinstance(d_errors, list)


def test_duplicate_claims_check() -> None:
    parsed = parse(SAMPLE_834_TEXT)
    dups = duplicate_member_check(parsed.loops)
    assert isinstance(dups, list)
