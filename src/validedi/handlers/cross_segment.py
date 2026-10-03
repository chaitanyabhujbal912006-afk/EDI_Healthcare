"""
Cross-segment validation handlers.
"""

import re
from datetime import datetime, timezone
from typing import Any

from validedi.engine.models import Loop, ValidationError


def charge_total_consistency(claim_loop: Loop) -> list[ValidationError]:
    """
    Verify that service line charges sum to claim total (837P and 837I).
    
    Auto-detects transaction type and uses appropriate segment (SV1 for 837P, SV2 for 837I).
    
    Args:
        claim_loop: 2300 claim loop
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Get CLM02 (total claim charge)
    clm_segment = claim_loop.find_segment('CLM')
    if not clm_segment:
        return errors
    
    try:
        claim_total = float(clm_segment.get_value(2))
    except (ValueError, IndexError):
        return errors
    
    # Sum service line charges from all 2400 service line loops
    service_line_total = 0.0
    service_line_loops = claim_loop.find_loop('2400')
    if not service_line_loops:
        errors.append(ValidationError(
            code='CLM_SUM_MISMATCH',
            severity='error',
            segment='CLM',
            element='CLM02',
            loop='2300',
            position=clm_segment.position,
            message=f'Claim {clm_segment.get_value(1)} has total charge ${claim_total:.2f} but no service lines (loop 2400 missing).',
        ))
        return errors
    
    for svc_loop in service_line_loops:
        # Try SV1 first (837P - professional)
        sv1_segment = svc_loop.find_segment('SV1')
        if sv1_segment:
            try:
                # SV102 is composite: charge*unit*quantity
                # Extract first component (charge amount)
                sv102_element = sv1_segment.get(2)
                if sv102_element.components:
                    # Has components - get first one
                    line_charge = float(sv102_element.components[0])
                else:
                    # No components - use raw value
                    line_charge = float(sv102_element.raw)
                service_line_total += line_charge
            except (ValueError, IndexError):
                continue
        else:
            # Try SV2 (837I - institutional)
            sv2_segment = svc_loop.find_segment('SV2')
            if sv2_segment:
                try:
                    # SV203 is the charge amount (simple value)
                    line_charge = float(sv2_segment.get_value(3))
                    service_line_total += line_charge
                except (ValueError, IndexError):
                    continue
    
    # Allow $0.01 tolerance for rounding
    if abs(claim_total - service_line_total) > 0.01:
        errors.append(ValidationError(
            code='CHARGE_TOTAL_CHECK',
            severity='error',
            segment='CLM',
            element='CLM02',
            loop='2300',
            position=clm_segment.position,
            message=f'Service line charges (${service_line_total:.2f}) do not match claim total (${claim_total:.2f})'
        ))
    
    return errors


def charge_total_consistency_i(claim_loop: Loop) -> list[ValidationError]:
    """
    Verify that service line charges sum to claim total (837I).
    
    Args:
        claim_loop: 2300 claim loop
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Get CLM02 (total claim charge)
    clm_segment = claim_loop.find_segment('CLM')
    if not clm_segment:
        return errors
    
    try:
        claim_total = float(clm_segment.get_value(2))
    except (ValueError, IndexError):
        return errors
    
    # Sum SV203 from all 2400 service line loops
    service_line_total = 0.0
    service_line_loops = claim_loop.find_loop('2400')
    if not service_line_loops:
        errors.append(ValidationError(
            code='CHARGE_TOTAL_CHECK_I',
            severity='error',
            segment='CLM',
            element='CLM02',
            loop='2300',
            position=clm_segment.position,
            message=f'Institutional claim {clm_segment.get_value(1)} has total charge ${claim_total:.2f} but no service lines (loop 2400 missing).',
        ))
        return errors
    
    for svc_loop in service_line_loops:
        sv2_segment = svc_loop.find_segment('SV2')
        if sv2_segment:
            try:
                # SV203 is the charge amount (simple value, not composite)
                line_charge = float(sv2_segment.get_value(3))
                service_line_total += line_charge
            except (ValueError, IndexError):
                continue
    
    # Allow $0.01 tolerance for rounding
    if abs(claim_total - service_line_total) > 0.01:
        errors.append(ValidationError(
            code='CHARGE_TOTAL_CHECK_I',
            severity='error',
            segment='CLM',
            element='CLM02',
            loop='2300',
            position=clm_segment.position,
            message=f'Service line charges (${service_line_total:.2f}) do not match claim total (${claim_total:.2f})'
        ))
    
    return errors



def date_range_check(start_date: str, end_date: str, context: str = '') -> list[ValidationError]:
    """
    Verify that start date is before or equal to end date.
    
    Args:
        start_date: Start date in CCYYMMDD format
        end_date: End date in CCYYMMDD format
        context: Context description for error message
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    try:
        start = datetime.strptime(start_date, '%Y%m%d').replace(tzinfo=timezone.utc)
        end = datetime.strptime(end_date, '%Y%m%d').replace(tzinfo=timezone.utc)
        
        if start > end:
            errors.append(ValidationError(
                code='DATE_RANGE_INVALID',
                severity='error',
                segment='DTP',
                element=None,
                loop=None,
                position=0,
                message=f'Start date {start_date} is after end date {end_date} {context}'
            ))
    except ValueError as e:
        errors.append(ValidationError(
            code='DATE_FORMAT_INVALID',
            severity='error',
            segment='DTP',
            element=None,
            loop=None,
            position=0,
            message=f'Invalid date format: {e!s}'
        ))
    
    return errors


def dob_vs_claim_date(source: Any, claim_date: str | None = None) -> list[ValidationError]:
    """
    Verify that date of birth is before claim date.
    Can be invoked either as a builtin handler receiving loops or with (dob, claim_date) strings.
    """
    if isinstance(source, list) or hasattr(source, 'segments'):
        loops = source if isinstance(source, list) else [source]
        dob_val: str | None = None
        claim_date_val: str | None = None
        dtp_pos = 0

        def search(lp: Loop) -> None:
            nonlocal dob_val, claim_date_val, dtp_pos
            for seg in lp.segments:
                if seg.segment_id == 'DMG' and len(seg.elements) > 1 and not dob_val:
                    raw_val = seg.get_value(2).strip()
                    if re.fullmatch(r'\d{8}', raw_val):
                        dob_val = raw_val
                if seg.segment_id == 'DTP' and len(seg.elements) > 2 and not claim_date_val:
                    qual = seg.get_value(1).strip()
                    if qual in {'434', '472'}:
                        date_str = seg.get_value(3).strip()
                        if '-' in date_str:
                            date_str = date_str.split('-')[0]
                        if re.fullmatch(r'\d{8}', date_str):
                            claim_date_val = date_str
                            dtp_pos = seg.position
            for ch in lp.children:
                search(ch)

        for l in loops:
            search(l)

        if dob_val and claim_date_val:
            try:
                b_dt = datetime.strptime(dob_val, '%Y%m%d').replace(tzinfo=timezone.utc)
                c_dt = datetime.strptime(claim_date_val, '%Y%m%d').replace(tzinfo=timezone.utc)
                if b_dt > c_dt:
                    return [
                        ValidationError(
                            code='DOB_AFTER_CLAIM',
                            severity='error',
                            segment='DTP',
                            element='DTP03',
                            loop='PATIENT',
                            position=dtp_pos,
                            message='Patient DOB occurs after claim service date.',
                        )
                    ]
            except (ValueError, TypeError):
                pass
        return []

    errors = []
    dob = str(source)
    claim_dt_str = claim_date or ''
    try:
        birth_date = datetime.strptime(dob, '%Y%m%d').replace(tzinfo=timezone.utc)
        claim_dt = datetime.strptime(claim_dt_str, '%Y%m%d').replace(tzinfo=timezone.utc)
        if birth_date > claim_dt:
            errors.append(ValidationError(
                code='DOB_AFTER_CLAIM',
                severity='error',
                segment='DTP',
                element='DTP03',
                loop='PATIENT',
                position=0,
                message='Patient DOB occurs after claim service date.',
            ))
    except ValueError as e:
        errors.append(ValidationError(
            code='DATE_FORMAT_INVALID',
            severity='error',
            segment='DMG',
            element='DMG02',
            loop=None,
            position=0,
            message=f'Invalid date format: {e!s}'
        ))
    return errors


def coverage_date_consistency(coverage_loop: Loop) -> list[ValidationError]:
    """
    Verify coverage start date is before or equal to end date
    within a 2300 HD loop in an 834 transaction (supports both D8 and RD8).
    """
    errors = []
    start_date = None
    end_date = None
    pos = coverage_loop.segments[0].position if coverage_loop.segments else 0

    for seg in coverage_loop.segments:
        if seg.segment_id == 'DTP':
            pos = seg.position
            qualifier = seg.get_value(1).strip()
            fmt = seg.get_value(2).strip()
            date_val = seg.get_value(3).strip()

            if fmt == 'RD8' and '-' in date_val:
                parts = date_val.split('-')
                if len(parts) >= 2:
                    start_date = parts[0].strip()
                    end_date = parts[1].strip()
            elif qualifier == '348':  # Coverage effective date
                start_date = date_val
            elif qualifier == '349':  # Coverage end date
                end_date = date_val

    if start_date and end_date:
        try:
            start = datetime.strptime(start_date, '%Y%m%d').replace(tzinfo=timezone.utc)
            end = datetime.strptime(end_date, '%Y%m%d').replace(tzinfo=timezone.utc)
            if start > end:
                errors.append(ValidationError(
                    code='DATE_RANGE_INVALID',
                    severity='error',
                    segment='DTP',
                    element='DTP03',
                    loop='2300',
                    position=pos,
                    message=f'Coverage end date {end_date} is before start date {start_date} (coverage dates)',
                ))
        except ValueError as e:
            errors.append(ValidationError(
                code='DATE_RANGE_INVALID',
                severity='error',
                segment='DTP',
                element='DTP03',
                loop='2300',
                position=pos,
                message=f'Invalid date format: {e!s}',
            ))

    return errors


def validate_hl_hierarchy(loops: list[Loop]) -> list[ValidationError]:
    """
    Validate 837 HL parent/child relationships and level codes:
    1. HL02 parent ID must reference an existing prior HL01.
    2. HL03 level sequence must follow 20 (Billing Provider) -> 22 (Subscriber) -> 23 (Dependent).
    3. Level 22 parent must be 20; Level 23 parent must be 22.
    """
    errors: list[ValidationError] = []
    all_segs: list[Any] = []

    def _collect(lp: Loop):
        all_segs.extend(lp.segments)
        for ch in lp.children:
            _collect(ch)

    if isinstance(loops, list):
        for lp in loops:
            _collect(lp)
    elif hasattr(loops, 'segments'):
        _collect(loops)

    hl_segs = [s for s in all_segs if s.segment_id == 'HL']
    seen_hl01: dict[str, str] = {}  # hl01 -> hl03 level

    for seg in hl_segs:
        hl01 = seg.get_value(1).strip()
        hl02 = seg.get_value(2).strip()
        hl03 = seg.get_value(3).strip()

        if not hl01:
            continue

        # Check HL02 parent reference
        if hl02:
            if hl02 not in seen_hl01:
                errors.append(ValidationError(
                    code='HL_HIERARCHY_INVALID',
                    severity='error',
                    segment='HL',
                    element='HL02',
                    loop='2000',
                    position=seg.position,
                    message=f"HL segment {hl01} references non-existent parent HL02 '{hl02}'.",
                ))
            else:
                parent_level = seen_hl01[hl02]
                if hl03 == '22' and parent_level != '20':
                    errors.append(ValidationError(
                        code='HL_HIERARCHY_INVALID',
                        severity='error',
                        segment='HL',
                        element='HL03',
                        loop='2000',
                        position=seg.position,
                        message=f"HL segment {hl01} (Subscriber) parent must be level 20, got {parent_level}.",
                    ))
                elif hl03 == '23' and parent_level != '22':
                    errors.append(ValidationError(
                        code='HL_HIERARCHY_INVALID',
                        severity='error',
                        segment='HL',
                        element='HL03',
                        loop='2000',
                        position=seg.position,
                        message=f"HL segment {hl01} (Dependent) parent must be level 22, got {parent_level}.",
                    ))
        else:
            # Top-level HL must be level 20
            if hl03 and hl03 != '20':
                errors.append(ValidationError(
                    code='HL_HIERARCHY_INVALID',
                    severity='error',
                    segment='HL',
                    element='HL03',
                    loop='2000',
                    position=seg.position,
                    message=f"Top-level HL segment {hl01} must have level 20 (Billing Provider), got {hl03}.",
                ))

        # Check level sequence: 23 cannot precede 22; 22 cannot precede 20
        if hl03 == '23' and '22' not in seen_hl01.values():
            errors.append(ValidationError(
                code='HL_HIERARCHY_INVALID',
                severity='error',
                segment='HL',
                element='HL03',
                loop='2000',
                position=seg.position,
                message=f"HL segment {hl01} with level 23 (Dependent) cannot appear before level 22 (Subscriber).",
            ))
        elif hl03 == '22' and '20' not in seen_hl01.values():
            errors.append(ValidationError(
                code='HL_HIERARCHY_INVALID',
                severity='error',
                segment='HL',
                element='HL03',
                loop='2000',
                position=seg.position,
                message=f"HL segment {hl01} with level 22 (Subscriber) cannot appear before level 20 (Billing Provider).",
            ))

        seen_hl01[hl01] = hl03

    return errors

