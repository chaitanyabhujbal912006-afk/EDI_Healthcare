"""
Cross-segment validation handlers.
"""

from datetime import datetime
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
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')
        
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
            message=f'Invalid date format: {str(e)}'
        ))
    
    return errors


def dob_vs_claim_date(dob: str, claim_date: str) -> list[ValidationError]:
    """
    Verify that date of birth is before claim date.
    
    Args:
        dob: Date of birth in CCYYMMDD format
        claim_date: Claim date in CCYYMMDD format
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    try:
        birth_date = datetime.strptime(dob, '%Y%m%d')
        claim_dt = datetime.strptime(claim_date, '%Y%m%d')
        
        if birth_date >= claim_dt:
            errors.append(ValidationError(
                code='DOB_VS_CLAIM_DATE',
                severity='error',
                segment='DMG',
                element='DMG02',
                loop=None,
                position=0,
                message=f'Date of birth {dob} must be before claim date {claim_date}'
            ))
    except ValueError as e:
        errors.append(ValidationError(
            code='DATE_FORMAT_INVALID',
            severity='error',
            segment='DMG',
            element='DMG02',
            loop=None,
            position=0,
            message=f'Invalid date format: {str(e)}'
        ))
    
    return errors


def coverage_date_consistency(coverage_loop: Loop) -> list[ValidationError]:
    """
    Verify coverage start date (DTP*348) is before or equal to end date (DTP*349)
    within a 2300 HD loop in an 834 transaction.

    Args:
        coverage_loop: 2300 loop containing DTP segments

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    start_date = None
    end_date = None

    for seg in coverage_loop.segments:
        if seg.segment_id == 'DTP':
            qualifier = seg.get_value(1)
            date_val = seg.get_value(3)
            if qualifier == '348':  # Coverage effective date
                start_date = date_val
            elif qualifier == '349':  # Coverage end date
                end_date = date_val

    if start_date and end_date:
        errors.extend(date_range_check(start_date, end_date, context='(coverage dates)'))

    return errors
