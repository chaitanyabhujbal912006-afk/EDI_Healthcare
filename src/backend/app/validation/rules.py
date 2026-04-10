from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

from app.models import ParseResult, ValidationIssue, ValidationResult
from app.parser.x12_parser import extract_claim_amounts_for_837

REQUIRED_SEGMENTS = {
    "837P": {"ISA", "GS", "ST", "BHT", "NM1", "CLM", "SE", "GE", "IEA"},
    "837I": {"ISA", "GS", "ST", "BHT", "NM1", "CLM", "SE", "GE", "IEA"},
    "835": {"ISA", "GS", "ST", "BPR", "TRN", "CLP", "SE", "GE", "IEA"},
    "834": {"ISA", "GS", "ST", "BGN", "INS", "SE", "GE", "IEA"},
}

VALID_CAS_GROUPS = {"PR", "CO", "OA", "PI"}
VALID_INS_CODES = {"001", "021", "024", "025", "030", "032", "033", "035"}
VALID_RELATIONSHIP_CODES = {"18", "01", "19", "20", "21", "53"}


def validate(parsed: ParseResult) -> ValidationResult:
    issues: list[ValidationIssue] = []
    segments = parsed.segments
    tx_type = parsed.transaction_type

    if tx_type == "UNKNOWN":
        issues.append(
            ValidationIssue(
                code="TXN_UNKNOWN",
                severity="error",
                message="Unable to detect transaction type from ST segment.",
                loop_location="ROOT",
                segment_id="ST",
            )
        )
        return ValidationResult(valid=False, issues=issues)

    _check_required_segments(parsed, issues)
    _check_element_formats(parsed, issues)
    _check_qualifiers(parsed, issues)
    _check_cross_segment_consistency(parsed, issues)

    if tx_type == "835":
        _check_835_rules(parsed, issues)
    if tx_type == "834":
        _check_834_rules(parsed, issues)

    return ValidationResult(valid=not any(i.severity == "error" for i in issues), issues=issues)


def _check_required_segments(parsed: ParseResult, issues: list[ValidationIssue]) -> None:
    present = {s.id for s in parsed.segments}
    required = REQUIRED_SEGMENTS.get(parsed.transaction_type, set())

    for seg in sorted(required - present):
        issues.append(
            ValidationIssue(
                code="REQ_SEG_MISSING",
                severity="error",
                message=f"Required segment {seg} is missing.",
                loop_location="ROOT",
                segment_id=seg,
                suggested_value=f"Add segment {seg} in the appropriate loop.",
            )
        )


def _check_element_formats(parsed: ParseResult, issues: list[ValidationIssue]) -> None:
    for seg in parsed.segments:
        if seg.id == "NM1" and len(seg.elements) > 8:
            nm108 = seg.elements[7]
            nm109 = seg.elements[8]
            if nm108 == "XX" and nm109 and not _valid_npi(nm109):
                issues.append(
                    ValidationIssue(
                        code="NPI_INVALID",
                        severity="error",
                        message="NM109 NPI is invalid. Expected 10-digit NPI with valid check digit.",
                        loop_location="NM1",
                        segment_id="NM1",
                        element_position=9,
                        current_value=nm109,
                    )
                )

        if seg.id == "N4" and len(seg.elements) > 2:
            zip_code = seg.elements[2]
            if zip_code and not re.fullmatch(r"\d{5}(\d{4})?", zip_code):
                issues.append(
                    ValidationIssue(
                        code="ZIP_INVALID",
                        severity="warning",
                        message="ZIP format should be 5 or 9 digits.",
                        loop_location="N4",
                        segment_id="N4",
                        element_position=3,
                        current_value=zip_code,
                    )
                )

        if seg.id == "DTP" and len(seg.elements) > 2:
            value = seg.elements[2]
            if seg.elements[1] == "D8" and not re.fullmatch(r"\d{8}", value):
                issues.append(
                    ValidationIssue(
                        code="DATE_FORMAT",
                        severity="error",
                        message="DTP date must be CCYYMMDD when DTP02 = D8.",
                        loop_location="DTP",
                        segment_id="DTP",
                        element_position=3,
                        current_value=value,
                    )
                )

        if seg.id in {"CLM", "SV1", "SV2", "CLP"} and len(seg.elements) > 1:
            amount = seg.elements[1]
            if amount and not re.fullmatch(r"\d+(\.\d{1,2})?", amount):
                issues.append(
                    ValidationIssue(
                        code="AMOUNT_FORMAT",
                        severity="error",
                        message="Amount must be numeric with up to 2 decimal places.",
                        loop_location=seg.id,
                        segment_id=seg.id,
                        element_position=2,
                        current_value=amount,
                    )
                )


def _check_qualifiers(parsed: ParseResult, issues: list[ValidationIssue]) -> None:
    for seg in parsed.segments:
        if seg.id == "NM1" and len(seg.elements) > 7:
            nm108 = seg.elements[7]
            if nm108 and nm108 not in {"XX", "FI", "46", "24", "34", "MI", "PI"}:
                issues.append(
                    ValidationIssue(
                        code="QUAL_NM108",
                        severity="warning",
                        message="NM108 qualifier is uncommon for HIPAA 5010 and may be invalid.",
                        loop_location="NM1",
                        segment_id="NM1",
                        element_position=8,
                        current_value=nm108,
                    )
                )

        if seg.id == "CLM" and len(seg.elements) > 4:
            clm05 = seg.elements[4]
            if clm05 and ":" in clm05:
                parts = clm05.split(":")
                facility = parts[0]
                frequency = parts[2] if len(parts) > 2 else ""
                if facility and not re.fullmatch(r"\d{2}", facility):
                    issues.append(
                        ValidationIssue(
                            code="QUAL_CLM05_FAC",
                            severity="warning",
                            message="CLM05-1 facility type should be 2 digits.",
                            loop_location="CLM",
                            segment_id="CLM",
                            element_position=5,
                            current_value=clm05,
                        )
                    )
                if frequency and frequency not in {"1", "7", "8"}:
                    issues.append(
                        ValidationIssue(
                            code="QUAL_CLM05_FREQ",
                            severity="warning",
                            message="CLM05-3 claim frequency code looks invalid.",
                            loop_location="CLM",
                            segment_id="CLM",
                            element_position=5,
                            current_value=clm05,
                        )
                    )

        if seg.id == "SV1" and seg.elements:
            proc = seg.elements[0]
            # Common pattern: HC:99213
            if proc and ":" in proc:
                _, code = proc.split(":", maxsplit=1)
                if code and not re.fullmatch(r"[A-Z0-9]{4,5}", code):
                    issues.append(
                        ValidationIssue(
                            code="QUAL_SVC01",
                            severity="warning",
                            message="SVC01 procedure code should look like valid CPT/HCPCS.",
                            loop_location="SV1",
                            segment_id="SV1",
                            element_position=1,
                            current_value=proc,
                        )
                    )


def _check_cross_segment_consistency(parsed: ParseResult, issues: list[ValidationIssue]) -> None:
    if parsed.transaction_type in {"837P", "837I"}:
        claim_total, svc_total = extract_claim_amounts_for_837(parsed.segments)
        if claim_total and svc_total and round(claim_total, 2) != round(svc_total, 2):
            issues.append(
                ValidationIssue(
                    code="CLM_SUM_MISMATCH",
                    severity="error",
                    message="CLM total charge does not match sum of service line charges.",
                    loop_location="CLAIM",
                    segment_id="CLM",
                    suggested_value=f"Adjust CLM02 to {svc_total:.2f} or fix SV1/SV2 line amounts.",
                )
            )

        dob = _find_dob(parsed)
        claim_date = _find_claim_date(parsed)
        if dob and claim_date and dob > claim_date:
            issues.append(
                ValidationIssue(
                    code="DOB_AFTER_CLAIM",
                    severity="error",
                    message="Patient DOB occurs after claim service date.",
                    loop_location="PATIENT",
                    segment_id="DTP",
                )
            )


def _check_835_rules(parsed: ParseResult, issues: list[ValidationIssue]) -> None:
    clp_billed = 0.0
    clp_paid = 0.0
    for seg in parsed.segments:
        if seg.id == "CAS" and seg.elements:
            group = seg.elements[0]
            if group not in VALID_CAS_GROUPS:
                issues.append(
                    ValidationIssue(
                        code="CAS_GROUP_INVALID",
                        severity="error",
                        message="CAS01 must be one of PR, CO, OA, PI.",
                        loop_location="CLP/CAS",
                        segment_id="CAS",
                        element_position=1,
                        current_value=group,
                    )
                )
        if seg.id == "CLP" and len(seg.elements) > 3:
            clp_billed += _to_float(seg.elements[2])
            clp_paid += _to_float(seg.elements[3])

    if clp_paid > clp_billed:
        issues.append(
            ValidationIssue(
                code="CLP_RECON_FAIL",
                severity="warning",
                message="Total paid amount exceeds billed amount; verify CLP reconciliation.",
                loop_location="CLP",
                segment_id="CLP",
            )
        )


def _check_834_rules(parsed: ParseResult, issues: list[ValidationIssue]) -> None:
    member_ids: list[str] = []

    for seg in parsed.segments:
        if seg.id == "INS" and len(seg.elements) > 2:
            maint = seg.elements[2]
            rel = seg.elements[1] if len(seg.elements) > 1 else ""
            if maint and maint not in VALID_INS_CODES:
                issues.append(
                    ValidationIssue(
                        code="INS_MAINT_INVALID",
                        severity="error",
                        message="INS03 maintenance type code is not valid.",
                        loop_location="2000",
                        segment_id="INS",
                        element_position=3,
                        current_value=maint,
                    )
                )
            if rel and rel not in VALID_RELATIONSHIP_CODES:
                issues.append(
                    ValidationIssue(
                        code="INS_REL_INVALID",
                        severity="warning",
                        message="INS02 relationship code looks invalid.",
                        loop_location="2000",
                        segment_id="INS",
                        element_position=2,
                        current_value=rel,
                    )
                )

        if seg.id == "REF" and len(seg.elements) > 1 and seg.elements[0] in {"0F", "1L"}:
            member_ids.append(seg.elements[1])

    counts = Counter(member_ids)
    dupes = [m for m, c in counts.items() if c > 1]
    for m in dupes:
        issues.append(
            ValidationIssue(
                code="MEMBER_DUPLICATE",
                severity="error",
                message="Duplicate subscriber/member identifier found in file.",
                loop_location="2000",
                segment_id="REF",
                current_value=m,
            )
        )


def _find_dob(parsed: ParseResult) -> datetime | None:
    for seg in parsed.segments:
        if seg.id == "DMG" and len(seg.elements) > 1 and re.fullmatch(r"\d{8}", seg.elements[1]):
            return _to_date(seg.elements[1])
    return None


def _find_claim_date(parsed: ParseResult) -> datetime | None:
    for seg in parsed.segments:
        if seg.id == "DTP" and len(seg.elements) > 2 and seg.elements[0] in {"434", "472"}:
            if re.fullmatch(r"\d{8}", seg.elements[2]):
                return _to_date(seg.elements[2])
    return None


def _to_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y%m%d")


def _valid_npi(npi: str) -> bool:
    if not re.fullmatch(r"\d{10}", npi):
        return False

    # NPI uses Luhn on 80840 + first 9 digits, checking the 10th.
    digits = [int(d) for d in "80840" + npi[:-1]]
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d

    check_digit = (10 - (checksum % 10)) % 10
    return check_digit == int(npi[-1])


def _to_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0

