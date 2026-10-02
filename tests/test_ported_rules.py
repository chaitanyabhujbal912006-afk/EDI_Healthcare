"""
Tests for all ported rules from legacy rules.py to validedi.
Ensures every rule code emitted by legacy validation is supported by validedi.
"""
from __future__ import annotations

from app.adapters import validate_edi_content
from test_api_endpoints import SAMPLE_834, SAMPLE_835, SAMPLE_837P


def test_sample_837p_and_sample_835_zero_errors() -> None:
    """sample_837p.edi and sample_835.edi must validate with zero errors."""
    with open("sample_837p.edi", "r", encoding="utf-8") as f:
        c837 = f.read()
    with open("sample_835.edi", "r", encoding="utf-8") as f:
        c835 = f.read()

    r837 = validate_edi_content(c837)
    r835 = validate_edi_content(c835)

    errors_837 = [i for i in r837.issues if i.severity == "error"]
    errors_835 = [i for i in r835.issues if i.severity == "error"]

    assert r837.valid is True
    assert len(errors_837) == 0
    assert r835.valid is True
    assert len(errors_835) == 0


def test_rule_se_count_mismatch() -> None:
    """SE01 count differs from actual count."""
    edi = SAMPLE_837P.replace("SE*25*0001~", "SE*99*0001~")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "SE_COUNT_MISMATCH" in codes


def test_rule_ge_count_mismatch() -> None:
    """GE01 count differs from actual ST count."""
    edi = SAMPLE_837P.replace("GE*1*1~", "GE*5*1~")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "GE_COUNT_MISMATCH" in codes


def test_rule_npi_invalid() -> None:
    """NPI with invalid check digit emits NPI_INVALID."""
    # 1234567890 fails Luhn algorithm check
    edi = SAMPLE_837P.replace("1992837465", "1234567890")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "NPI_INVALID" in codes


def test_rule_billing_npi_required() -> None:
    """Billing provider NM1*85 missing qualifier XX or NPI emits BILLING_NPI_REQUIRED."""
    edi = SAMPLE_837P.replace("*****XX*1992837465~", "*****ZZ*1992837465~")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "BILLING_NPI_REQUIRED" in codes


def test_rule_zip_invalid() -> None:
    """N403 with invalid ZIP emits ZIP_INVALID."""
    edi = SAMPLE_837P.replace("N4*METROPOLIS*NY*10001~", "N4*METROPOLIS*NY*1001~")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "ZIP_INVALID" in codes


def test_rule_date_format() -> None:
    """DTP segment with DTP02=D8 but invalid 8-digit date emits DATE_FORMAT."""
    edi = SAMPLE_837P.replace("DTP*472*D8*20260820~", "DTP*472*D8*2026820~")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "DATE_FORMAT" in codes


def test_rule_amount_format() -> None:
    """Non-numeric or malformed amount in CLM/SV1 emits AMOUNT_FORMAT."""
    edi = SAMPLE_837P.replace("1250.00", "1250.005")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "AMOUNT_FORMAT" in codes


def test_rule_qual_nm108() -> None:
    """Unrecognized qualifier in NM108 emits QUAL_NM108."""
    edi = SAMPLE_837P.replace("*****46*1234567890~", "*****99*1234567890~")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "QUAL_NM108" in codes


def test_rule_qual_clm05_fac_and_freq() -> None:
    """Invalid facility type or frequency code in CLM05 emits QUAL_CLM05_FAC / QUAL_CLM05_FREQ."""
    edi = SAMPLE_837P.replace("11:B:1", "1:B:9")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "QUAL_CLM05_FAC" in codes or "QUAL_CLM05_FREQ" in codes


def test_rule_qual_svc01() -> None:
    """Invalid procedure code in SV101 emits QUAL_SVC01."""
    edi = SAMPLE_837P.replace("SV1*HC:99214*", "SV1*HC:1*")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "QUAL_SVC01" in codes


def test_rule_clm_sum_mismatch() -> None:
    """CLM02 does not match sum of service lines emits CLM_SUM_MISMATCH."""
    edi = SAMPLE_837P.replace("CLM*CLM-99401*1250.00***", "CLM*CLM-99401*5000.00***")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "CLM_SUM_MISMATCH" in codes


def test_rule_dob_after_claim() -> None:
    """Patient DOB after claim service date emits DOB_AFTER_CLAIM."""
    # DOB 20300101 > service date 20260820
    edi = SAMPLE_837P.replace("DMG*D8*19800512*M~", "DMG*D8*20300101*M~")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "DOB_AFTER_CLAIM" in codes


def test_rule_cas_group_invalid() -> None:
    """Invalid CAS01 group code emits CAS_GROUP_INVALID."""
    edi = SAMPLE_835.replace("CAS*CO*45*250.00~", "CAS*XX*45*250.00~")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "CAS_GROUP_INVALID" in codes


def test_rule_clp_recon_fail() -> None:
    """CLP04 (paid) > CLP03 (billed) emits CLP_RECON_FAIL."""
    # Billed 1250, paid 2000
    edi = SAMPLE_835.replace("1250.00*1000.00*", "1250.00*2000.00*")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "CLP_RECON_FAIL" in codes


def test_rule_ins_maint_invalid() -> None:
    """Invalid INS03 maintenance type code emits INS_MAINT_INVALID."""
    edi = SAMPLE_834.replace("INS*Y*18*001*", "INS*Y*18*999*")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "INS_MAINT_INVALID" in codes


def test_rule_ins_rel_invalid() -> None:
    """Invalid INS02 relationship code emits INS_REL_INVALID."""
    edi = SAMPLE_834.replace("INS*Y*18*001*", "INS*Y*99*001*")
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "INS_REL_INVALID" in codes


def test_rule_member_duplicate() -> None:
    """Duplicate member ID emits MEMBER_DUPLICATE."""
    edi = SAMPLE_834 + "INS*Y*18*001*28*A***FT~REF*0F*MEMB1001~SE*11*0003~GE*1*3~IEA*1*000000003~"
    result = validate_edi_content(edi)
    codes = [i.code for i in result.issues]
    assert "MEMBER_DUPLICATE" in codes


def test_rule_txn_unknown() -> None:
    """EDI with unknown transaction type emits TXN_UNKNOWN."""
    bad_edi = (
        "ISA*00*          *00*          *ZZ*SUBMITTER1     *ZZ*RECEIVER1      *260824*1030*U*00501*000000001*0*P*>~\n"
        "GS*XX*SUBMITTER1*RECEIVER1*20260824*1030*1*X*005010X222A1~\n"
        "ST*999*0001~\n"
        "SE*2*0001~\n"
        "GE*1*1~\n"
        "IEA*1*000000001~"
    )
    result = validate_edi_content(bad_edi)
    assert result.valid is False
    codes = [i.code for i in result.issues]
    assert "TXN_UNKNOWN" in codes
