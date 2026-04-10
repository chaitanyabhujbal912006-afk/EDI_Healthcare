"""
Diagnosis code validation handlers with date-aware ICD-9/ICD-10 support.
"""

import re
from datetime import datetime
from validedi.engine.models import Loop, ValidationError


# ICD-9 pattern: 3-5 digits with optional decimal, or E/V codes
# Examples: 250, 250.00, 8842, E884.2, V70.0
ICD9_PATTERN = re.compile(r'^[0-9]{3,5}(\.[0-9]{1,2})?$|^[EV][0-9]{3,4}(\.[0-9]{1,2})?$')

# ICD-10 pattern: Letter + 2 alphanumeric + optional decimal + 1-4 alphanumeric
# Examples: I10, Z87.00, M54.30, S06.0X0A
ICD10_PATTERN = re.compile(r'^([A-Z]{3}:)?[A-TV-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?$')

# ICD-10 transition date (October 1, 2015)
ICD10_TRANSITION_DATE = datetime(2015, 10, 1)


def validate_diagnosis_code(claim_loop: Loop) -> list[ValidationError]:
    """
    Validate diagnosis codes with date-aware ICD-9/ICD-10 checking.
    
    Uses service date to determine which ICD version to validate against:
    - Before 2015-10-01: ICD-9
    - On or after 2015-10-01: ICD-10
    
    Args:
        claim_loop: 2300 claim loop containing HI and DTP segments
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Find HI segment (diagnosis codes)
    hi_segment = claim_loop.find_segment('HI')
    if not hi_segment:
        return errors
    
    # Determine ICD version based on service date
    icd_version = _determine_icd_version(claim_loop)
    
    # Validate each diagnosis code element (HI01-HI12)
    for i in range(1, 13):
        element = hi_segment.get(i)
        if not element.raw:
            continue
        
        # Extract code from qualifier:code format (e.g., "ABK:I10" -> "I10" or "BK:8842" -> "8842")
        code = element.raw
        if ':' in code:
            parts = code.split(':', 1)
            if len(parts) > 1:
                code = parts[1]
        
        # Skip empty codes
        if not code:
            continue
        
        # Validate based on ICD version
        is_valid = False
        if icd_version == 'ICD-9':
            is_valid = ICD9_PATTERN.match(code) is not None
        else:  # ICD-10
            is_valid = ICD10_PATTERN.match(code) is not None
        
        if not is_valid:
            errors.append(ValidationError(
                code='DIAGNOSIS_CODE_FORMAT',
                severity='error',
                segment='HI',
                element=f'HI{i:02d}',
                loop='2300',
                position=hi_segment.position,
                message=f'{icd_version} code {code} does not match required format (full value: {element.raw})'
            ))
    
    return errors


def _determine_icd_version(claim_loop: Loop) -> str:
    """
    Determine which ICD version to use based on service date.
    
    Args:
        claim_loop: 2300 claim loop
        
    Returns:
        'ICD-9' or 'ICD-10'
    """
    # Look for service date in DTP segments
    # DTP*472 = Service Date
    for child in claim_loop.children:
        if child.loop_id == '2400':  # Service line loop
            dtp = child.find_segment('DTP')
            if dtp and dtp.get_value(1) == '472':
                service_date_str = dtp.get_value(3)
                if service_date_str:
                    try:
                        # Parse date (format: CCYYMMDD or CCYYMMDD-CCYYMMDD)
                        if '-' in service_date_str:
                            service_date_str = service_date_str.split('-')[0]
                        
                        service_date = datetime.strptime(service_date_str, '%Y%m%d')
                        
                        # Compare to ICD-10 transition date
                        if service_date >= ICD10_TRANSITION_DATE:
                            return 'ICD-10'
                        else:
                            return 'ICD-9'
                    except ValueError:
                        pass
    
    # Also check claim-level DTP segments
    dtp_segments = claim_loop.find_all('DTP')
    for dtp in dtp_segments:
        if dtp.get_value(1) == '472':  # Service date
            service_date_str = dtp.get_value(3)
            if service_date_str:
                try:
                    if '-' in service_date_str:
                        service_date_str = service_date_str.split('-')[0]
                    
                    service_date = datetime.strptime(service_date_str, '%Y%m%d')
                    
                    if service_date >= ICD10_TRANSITION_DATE:
                        return 'ICD-10'
                    else:
                        return 'ICD-9'
                except ValueError:
                    pass
    
    # Default to ICD-10 for current claims (no date found)
    return 'ICD-10'
