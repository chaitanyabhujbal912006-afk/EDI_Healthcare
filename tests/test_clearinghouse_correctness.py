"""
Tests for clearinghouse correctness gaps in validedi:
1. Delimiter-in-data check using DelimiterSet from detector.
2. Multiple GS groups and multiple ISA interchanges per file (SE/GE/IEA control counts and matching).
3. 835: PLB provider-level adjustments in payment balancing (BPR02 == CLP04 sum - PLB adjustments).
4. 837: HL parent/child validity (HL02 references valid HL01, 20 -> 22 -> 23 sequence) and CLM with no lines.
5. Date/time checks: ISA09 YYMMDD, ISA10 HHMM, GS04 CCYYMMDD, DTP D8/RD8 (end >= start).
6. 834: INS/HD/DTP coverage dates (end >= start) and duplicate member detection across HD loops.
"""

from validedi.engine.parser import parse
from validedi.engine.validator import validate

# ── Fixtures & Helpers ────────────────────────────────────────────────────────

def make_valid_835(bpr="450.00", clp="450.00", plb_segment="") -> str:
    """Synthetic 835 remittance."""
    return (
        "ISA*00*          *00*          *ZZ*PAYER999        *ZZ*PROVIDER111    *230102*0900*^*00501*000000002*0*P*:~"
        "GS*HP*PAYER999*PROVIDER111*20230102*0900*2*X*005010X221A1~"
        "ST*835*0001*005010X221A1~"
        f"BPR*I*{bpr}*C*ACH*CCP*01*111111111*DA*11111111*20230102**01*222222222*DA*22222222~"
        "TRN*1*CHECK12345*1234567890~"
        "DTM*405*20230102~"
        "N1*PR*BLUE CROSS PAYER*XV*987654321~"
        "N1*PE*GENERAL HOSPITAL*XX*1234567893~"
        "LX*1~"
        f"CLP*CLAIM001*1*500.00*{clp}**MC*CLAIM001REF~"
        "NM1*QC*1*DOE*JOHN~"
        "SVC*HC:99213*150.00*135.00**1~"
        "DTM*472*20230101~"
        "CAS*CO*45*15.00~"
        "AMT*B6*135.00~"
        f"{plb_segment}"
        "SE*18*0001~"
        "GE*1*2~"
        "IEA*1*000000002~"
    )


def make_valid_837p(hl_segments: str | None = None, clm_segment: str | None = None, service_lines: str | None = None) -> str:
    """Synthetic 837P claim."""
    if hl_segments is None:
        hl_segments = (
            "HL*1**20*1~"
            "PRV*BI*PXC*207Q00000X~"
            "NM1*85*2*DOC CLINIC*****XX*1234567893~"
            "N3*100 MAIN ST~"
            "N4*ANYTOWN*OH*44101~"
            "HL*2*1*22*0~"
            "SBR*P*18*******CI~"
            "NM1*IL*1*SMITH*JANE****MI*MEM12345~"
            "DMG*D8*19800101*F~"
            "NM1*PR*PAYER ABC*****PI*PAY123~"
        )
    if clm_segment is None:
        clm_segment = "CLM*CLAIM001*100.00***11:B:1*Y*A*Y*Y~"
    if service_lines is None:
        service_lines = (
            "LX*1~"
            "SV1*HC:99213*100.00*UN*1~~~1~"
            "DTP*472*D8*20230101~"
        )
    return (
        "ISA*00*          *00*          *ZZ*SUBMITTER1     *ZZ*RECEIVER1      *230101*1200*^*00501*000000001*0*P*:~"
        "GS*HC*SUBMITTER1*RECEIVER1*20230101*1200*1*X*005010X222A1~"
        "ST*837*0001*005010X222A1~"
        "BHT*0019*00*123456*20230101*1200*CH~"
        "NM1*41*2*SUBMITTER NAME*****46*SUBID~"
        "PER*IC*EDI DEPT*TE*8005551212~"
        "NM1*40*2*RECEIVER NAME*****46*RECID~"
        f"{hl_segments}"
        f"{clm_segment}"
        "HI*ABK:I10~"
        f"{service_lines}"
        "SE*25*0001~"
        "GE*1*1~"
        "IEA*1*000000001~"
    )


def make_valid_834(dtp_segments: str = "DTP*348*D8*20230101~DTP*349*D8*20231231~", member_id: str = "MEM999") -> str:
    """Synthetic 834 enrollment."""
    return (
        "ISA*00*          *00*          *ZZ*SPONSOR        *ZZ*INSURER        *230101*1200*^*00501*000000001*0*P*:~"
        "GS*BE*SPONSOR*INSURER*20230101*1200*1*X*005010X220A1~"
        "ST*834*0001*005010X220A1~"
        "BGN*00*12345*20230101*1200****2~"
        "N1*P5*ACME CORP*FI*123456789~"
        "N1*IN*INSURER CORP*XV*987654321~"
        "INS*Y*18*030*XN*A~"
        f"REF*0F*{member_id}~"
        "NM1*IL*1*DOE*JOHN****MI*MEM123~"
        "DMG*D8*19800101*M~"
        "HD*030**HLT~"
        f"{dtp_segments}"
        "SE*13*0001~"
        "GE*1*1~"
        "IEA*1*000000001~"
    )


# ── 1. Delimiter-in-Data Check ────────────────────────────────────────────────

def test_delimiter_collision_with_detected_delimiters():
    """Element value containing element delimiter must trigger ENV-DELIM-COLLISION."""
    edi = (
        "ISA*00*          *00*          *ZZ*SUBMITTER1     *ZZ*RECEIVER1      *230101*1200*^*00501*000000001*0*P*:~"
        "GS*HC*SUBMITTER1*RECEIVER1*20230101*1200*1*X*005010X222A1~"
        "ST*837*0001*005010X222A1~"
        "BHT*0019*00*123456*20230101*1200*CH~"
        "SE*3*0001~"
        "GE*1*1~"
        "IEA*1*000000001~"
    )
    parsed = parse(edi)
    from validedi.engine.models import Element
    parsed.loops[0].segments[0].elements[1] = Element(raw="DOE*JOHN")
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert "ENV-DELIM-COLLISION" in codes


# ── 2. Multiple GS Groups and Multiple ISA Interchanges ───────────────────────

def test_multiple_gs_groups_independent_counts_valid():
    """File with multiple GS groups where each GE01 matches its own group's ST count."""
    edi = (
        "ISA*00*          *00*          *ZZ*SUBMITTER1     *ZZ*RECEIVER1      *230101*1200*^*00501*000000001*0*P*:~"
        # Functional group 1: 2 transaction sets
        "GS*HC*SUBMITTER1*RECEIVER1*20230101*1200*1*X*005010X222A1~"
        "ST*837*0001*005010X222A1~"
        "BHT*0019*00*123456*20230101*1200*CH~"
        "SE*3*0001~"
        "ST*837*0002*005010X222A1~"
        "BHT*0019*00*123457*20230101*1200*CH~"
        "SE*3*0002~"
        "GE*2*1~"  # 2 STs in Group 1, GE02=1 matches GS06=1
        # Functional group 2: 1 transaction set
        "GS*HC*SUBMITTER1*RECEIVER1*20230101*1200*2*X*005010X222A1~"
        "ST*837*0003*005010X222A1~"
        "BHT*0019*00*123458*20230101*1200*CH~"
        "SE*3*0003~"
        "GE*1*2~"  # 1 ST in Group 2, GE02=2 matches GS06=2
        "IEA*2*000000001~"  # 2 groups in ISA, IEA02 matches ISA13
    )
    parsed = parse(edi)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    # Neither GE count nor control match should fire
    assert "GE_COUNT_MISMATCH" not in codes
    assert "CTL-002" not in codes
    assert "IEA_COUNT_MISMATCH" not in codes


def test_multiple_gs_groups_ge_count_mismatch():
    """Group 2 has 1 ST but declares GE*2*2~, must fire GE_COUNT_MISMATCH."""
    edi = (
        "ISA*00*          *00*          *ZZ*SUBMITTER1     *ZZ*RECEIVER1      *230101*1200*^*00501*000000001*0*P*:~"
        "GS*HC*SUBMITTER1*RECEIVER1*20230101*1200*1*X*005010X222A1~"
        "ST*837*0001*005010X222A1~"
        "BHT*0019*00*123456*20230101*1200*CH~"
        "SE*3*0001~"
        "GE*1*1~"
        "GS*HC*SUBMITTER1*RECEIVER1*20230101*1200*2*X*005010X222A1~"
        "ST*837*0002*005010X222A1~"
        "BHT*0019*00*123457*20230101*1200*CH~"
        "SE*3*0002~"
        "GE*2*2~"  # Declared 2, but only 1 ST in group 2!
        "IEA*2*000000001~"
    )
    parsed = parse(edi)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert "GE_COUNT_MISMATCH" in codes


def test_multiple_isa_interchanges_iea_count():
    """IEA01 must match count of GS groups in that interchange."""
    edi = (
        "ISA*00*          *00*          *ZZ*SUBMITTER1     *ZZ*RECEIVER1      *230101*1200*^*00501*000000001*0*P*:~"
        "GS*HC*SUBMITTER1*RECEIVER1*20230101*1200*1*X*005010X222A1~"
        "ST*837*0001*005010X222A1~"
        "BHT*0019*00*123456*20230101*1200*CH~"
        "SE*3*0001~"
        "GE*1*1~"
        "IEA*5*000000001~"  # Declared 5 groups, only 1 actual group!
    )
    parsed = parse(edi)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert "IEA_COUNT_MISMATCH" in codes


# ── 3. 835: PLB Provider-Level Adjustments ─────────────────────────────────────

def test_835_plb_balancing_valid():
    """BPR02 ($450.00) equals CLP04 ($500.00) minus PLB adjustment ($50.00)."""
    # PLB*ProviderID*FiscalYearEnd*AdjustmentReasonCode:Ref*AdjustmentAmount~
    plb = "PLB*1234567893*20231231*WO:123*50.00~"
    edi = make_valid_835(bpr="450.00", clp="500.00", plb_segment=plb)
    parsed = parse(edi)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert "835-007" not in codes


def test_835_plb_balancing_invalid():
    """BPR02 ($500.00) does not equal CLP04 ($500.00) minus PLB adjustment ($50.00 = $450.00)."""
    plb = "PLB*1234567893*20231231*WO:123*50.00~"
    edi = make_valid_835(bpr="500.00", clp="500.00", plb_segment=plb)
    parsed = parse(edi)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert "835-007" in codes


# ── 4. 837: HL Parent/Child Validity and CLM Line Sum ─────────────────────────

def test_837_hl_parent_not_found():
    """HL02 references non-existent HL01 ID -> must trigger HL_HIERARCHY_INVALID."""
    hl_bad_parent = (
        "HL*1**20*1~"
        "PRV*BI*PXC*207Q00000X~"
        "NM1*85*2*DOC CLINIC*****XX*1234567893~"
        "N3*100 MAIN ST~"
        "N4*ANYTOWN*OH*44101~"
        "HL*2*99*22*0~"  # Parent 99 does not exist!
        "SBR*P*18*******CI~"
        "NM1*IL*1*SMITH*JANE****MI*MEM12345~"
        "DMG*D8*19800101*F~"
        "NM1*PR*PAYER ABC*****PI*PAY123~"
    )
    edi = make_valid_837p(hl_segments=hl_bad_parent)
    parsed = parse(edi)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert "HL_HIERARCHY_INVALID" in codes


def test_837_hl_invalid_level_sequence():
    """HL sequence cannot jump to 23 without a 22 subscriber parent."""
    hl_invalid_seq = (
        "HL*1**20*1~"
        "PRV*BI*PXC*207Q00000X~"
        "NM1*85*2*DOC CLINIC*****XX*1234567893~"
        "N3*100 MAIN ST~"
        "N4*ANYTOWN*OH*44101~"
        "HL*2*1*23*0~"  # Level 23 (Dependent) directly under 20 (Billing Provider) without 22!
        "SBR*P*18*******CI~"
        "NM1*IL*1*SMITH*JANE****MI*MEM12345~"
        "DMG*D8*19800101*F~"
        "NM1*PR*PAYER ABC*****PI*PAY123~"
    )
    edi = make_valid_837p(hl_segments=hl_invalid_seq)
    parsed = parse(edi)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert "HL_HIERARCHY_INVALID" in codes


def test_837_clm_no_service_lines_is_error():
    """Claim with total $100 but 0 service lines must fire CLM_SUM_MISMATCH."""
    edi = make_valid_837p(service_lines="")  # Empty service lines
    parsed = parse(edi)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert "CLM_SUM_MISMATCH" in codes


# ── 5. Date / Time Checks: ISA09, ISA10, GS04, DTP RD8 ────────────────────────

def test_isa09_date_format_invalid():
    """ISA09 must be YYMMDD with valid date."""
    edi = make_valid_837p().replace("*230101*1200*", "*230230*1200*")  # Feb 30 does not exist
    parsed = parse(edi)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert "FORMAT_ISA09_DATE" in codes


def test_isa10_time_format_invalid():
    """ISA10 must be HHMM with valid time (00-23, 00-59)."""
    edi = make_valid_837p().replace("*230101*1200*", "*230101*2599*")  # 25:99 is invalid time
    parsed = parse(edi)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert "FORMAT_ISA10_TIME" in codes


def test_gs04_date_format_invalid():
    """GS04 must be CCYYMMDD with valid 8-digit calendar date."""
    edi = make_valid_837p().replace("*20230101*1200*1*X*", "*20231332*1200*1*X*")  # Month 13 Day 32
    parsed = parse(edi)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert "FORMAT_GS04_DATE" in codes


def test_dtp_rd8_range_invalid():
    """DTP RD8 where end date < start date must trigger DTP_RANGE_INVALID."""
    edi = make_valid_837p(service_lines=(
        "LX*1~"
        "SV1*HC:99213*100.00*UN*1~~~1~"
        "DTP*472*RD8*20230601-20230501~"  # End is before start
    ))
    parsed = parse(edi)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert "DTP_RANGE_INVALID" in codes


# ── 6. 834: Coverage Dates and Duplicate Member Detection ─────────────────────

def test_834_coverage_dates_end_before_start():
    """Coverage end date before start date must trigger COVERAGE_DATE_CONSISTENCY."""
    edi = make_valid_834(dtp_segments="DTP*348*D8*20231231~DTP*349*D8*20230101~")
    parsed = parse(edi)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert "COVERAGE_DATE_CONSISTENCY" in codes


def test_834_duplicate_member_across_loops():
    """Same member ID across multiple 2000 loops must trigger MEMBER_DUPLICATE."""
    edi = (
        "ISA*00*          *00*          *ZZ*SPONSOR        *ZZ*INSURER        *230101*1200*^*00501*000000001*0*P*:~"
        "GS*BE*SPONSOR*INSURER*20230101*1200*1*X*005010X220A1~"
        "ST*834*0001*005010X220A1~"
        "BGN*00*12345*20230101*1200****2~"
        "N1*P5*ACME CORP*FI*123456789~"
        "N1*IN*INSURER CORP*XV*987654321~"
        # Member 1
        "INS*Y*18*030*XN*A~"
        "REF*0F*MEM12345~"
        "NM1*IL*1*DOE*JOHN****MI*MEM12345~"
        "DMG*D8*19800101*M~"
        "HD*030**HLT~"
        "DTP*348*D8*20230101~"
        # Member 2 (Duplicate ID!)
        "INS*N*19*030*XN*A~"
        "REF*0F*MEM12345~"
        "NM1*IL*1*DOE*JANE****MI*MEM12345~"
        "DMG*D8*20100101*F~"
        "HD*030**HLT~"
        "DTP*348*D8*20230101~"
        "SE*20*0001~"
        "GE*1*1~"
        "IEA*1*000000001~"
    )
    parsed = parse(edi)
    result = validate(parsed)
    codes = [e.code for e in result.errors]
    assert "MEMBER_DUPLICATE" in codes or "DUPLICATE_MEMBER_CHECK" in codes


# ── Sample Files Unchanged Behavior Check ─────────────────────────────────────

def test_sample_files_validate_with_zero_errors():
    """Verify repo root sample_837p.edi and sample_835.edi still validate with 0 errors."""
    from pathlib import Path
    root = Path(__file__).parent.parent
    sample_837 = root / "sample_837p.edi"
    sample_835 = root / "sample_835.edi"

    p837 = parse(sample_837)
    r837 = validate(p837)
    assert len(r837.errors) == 0, f"sample_837p.edi has errors: {[(e.code, e.message) for e in r837.errors]}"

    p835 = parse(sample_835)
    r835 = validate(p835)
    assert len(r835.errors) == 0, f"sample_835.edi has errors: {[(e.code, e.message) for e in r835.errors]}"
