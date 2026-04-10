"""
837I (Institutional Claims) data extractor.

Extracts structured claim data for hospital/facility claims.
"""

from typing import Any


def extract_claims_837i(parsed_edi) -> list[dict[str, Any]]:
    """
    Extract structured claim data from 837I transaction.
    
    Returns list of claims with:
    - Claim ID, totals, dates
    - Patient demographics
    - Facility information
    - Diagnosis codes
    - Service lines with revenue codes and charges
    - Admission/discharge information
    
    Args:
        parsed_edi: ParsedEDI object
        
    Returns:
        List of claim dictionaries
    """
    claims = []
    
    # Navigate loop hierarchy: 2000A -> 2000B -> 2300 (claims)
    for billing_loop in parsed_edi.loops:
        if billing_loop.loop_id == '2000A':
            # Extract billing provider/facility info
            billing_provider = _extract_facility_info(billing_loop)
            
            for subscriber_loop in billing_loop.children:
                if subscriber_loop.loop_id == '2000B':
                    # Extract subscriber/patient info
                    subscriber = _extract_patient_info(subscriber_loop)
                    
                    for claim_loop in subscriber_loop.children:
                        if claim_loop.loop_id == '2300':
                            claim = _extract_claim_837i(claim_loop)
                            claim['billing_provider'] = billing_provider
                            claim['patient'] = subscriber
                            claims.append(claim)
    
    return claims


def _extract_claim_837i(claim_loop) -> dict[str, Any]:
    """Extract data from a 2300 institutional claim loop."""
    clm = claim_loop.find_segment('CLM')
    hi = claim_loop.find_segment('HI')
    
    claim = {
        'claim_id': clm.get_value(1) if clm else None,
        'total_charge': _parse_amount(clm.get_value(2)) if clm else 0.0,
        'place_of_service': None,
        'bill_type': None,
        'claim_frequency': None,
        'admission_date': None,
        'discharge_date': None,
        'admission_type': None,
        'diagnoses': [],
        'service_lines': [],
    }
    
    # Extract place of service and bill type from CLM05
    if clm:
        clm05 = clm.get(5)
        if clm05.components:
            claim['place_of_service'] = clm05.get(1)
            claim['bill_type'] = clm05.get(2) if len(clm05.components) >= 2 else None
            claim['claim_frequency'] = clm05.get(3) if len(clm05.components) >= 3 else None
    
    # Extract admission/discharge dates from DTP segments
    dtp_segments = claim_loop.find_all('DTP')
    for dtp in dtp_segments:
        qualifier = dtp.get_value(1)
        date_value = dtp.get_value(3)
        
        if qualifier == '435':  # Admission date
            claim['admission_date'] = date_value
        elif qualifier == '096':  # Discharge date
            claim['discharge_date'] = date_value
    
    # Extract diagnosis codes from HI segment
    if hi:
        claim['diagnoses'] = _extract_diagnosis_codes(hi)
    
    # Extract service lines from 2400 loops
    for service_loop in claim_loop.children:
        if service_loop.loop_id == '2400':
            service_line = _extract_service_line_837i(service_loop)
            if service_line:
                claim['service_lines'].append(service_line)
    
    return claim


def _extract_service_line_837i(service_loop) -> dict[str, Any] | None:
    """Extract data from a 2400 institutional service line loop."""
    sv2 = service_loop.find_segment('SV2')
    if not sv2:
        return None
    
    # Extract revenue code from SV201
    revenue_code = sv2.get_value(1)
    
    # Extract procedure code from SV202 (composite: qualifier:code)
    sv202 = sv2.get(2)
    procedure_code = None
    if sv202.components:
        # Format: HC:99201 -> extract 99201
        procedure_code = sv202.components[-1] if sv202.components else sv202.raw
    else:
        procedure_code = sv202.raw
    
    # Extract charge from SV203 (simple value, not composite)
    charge = _parse_amount(sv2.get_value(3))
    
    # Extract units from SV205
    units = sv2.get_value(5)
    
    # Extract service date from DTP segment
    service_date = None
    dtp = service_loop.find_segment('DTP')
    if dtp and dtp.get_value(1) == '472':  # Service date qualifier
        service_date = dtp.get_value(3)
    
    return {
        'revenue_code': revenue_code,
        'procedure_code': procedure_code,
        'charge': charge,
        'units': units,
        'service_date': service_date,
    }


def _extract_facility_info(facility_loop) -> dict[str, Any]:
    """Extract facility/billing provider information."""
    nm1 = facility_loop.find_segment('NM1')
    n3 = facility_loop.find_segment('N3')
    n4 = facility_loop.find_segment('N4')
    ref = facility_loop.find_segment('REF')
    
    facility = {}
    
    if nm1:
        facility['name'] = nm1.get_value(3)
        facility['npi'] = nm1.get_value(9)
    
    if n3:
        facility['address'] = n3.get_value(1)
    
    if n4:
        facility['city'] = n4.get_value(1)
        facility['state'] = n4.get_value(2)
        facility['zip'] = n4.get_value(3)
    
    if ref and ref.get_value(1) == 'EI':
        facility['tax_id'] = ref.get_value(2)
    
    return facility


def _extract_patient_info(patient_loop) -> dict[str, Any]:
    """Extract patient information."""
    nm1 = patient_loop.find_segment('NM1')
    dmg = patient_loop.find_segment('DMG')
    n3 = patient_loop.find_segment('N3')
    n4 = patient_loop.find_segment('N4')
    ref = patient_loop.find_segment('REF')
    
    patient = {}
    
    if nm1:
        patient['last_name'] = nm1.get_value(3)
        patient['first_name'] = nm1.get_value(4)
        patient['member_id'] = nm1.get_value(9)
    
    if dmg:
        patient['dob'] = dmg.get_value(2)
        patient['gender'] = dmg.get_value(3)
    
    if n3:
        patient['address'] = n3.get_value(1)
    
    if n4:
        patient['city'] = n4.get_value(1)
        patient['state'] = n4.get_value(2)
        patient['zip'] = n4.get_value(3)
    
    if ref and ref.get_value(1) == 'SY':  # SSN
        patient['ssn'] = ref.get_value(2)
    
    return patient


def _extract_diagnosis_codes(hi_segment) -> list[dict[str, str]]:
    """Extract diagnosis codes from HI segment."""
    codes = []
    
    # HI can have up to 12 diagnosis codes (HI01-HI12)
    for i in range(1, 13):
        element = hi_segment.get(i)
        if not element.raw:
            continue
        
        # Format: BK:8842 -> extract qualifier and code
        qualifier = None
        code = element.raw
        
        if ':' in element.raw:
            parts = element.raw.split(':', 1)
            qualifier = parts[0]
            code = parts[1] if len(parts) > 1 else code
        
        # Determine diagnosis type from qualifier
        diagnosis_type = 'Additional'
        if i == 1 or qualifier in ('ABK', 'BK'):
            diagnosis_type = 'Primary'
        elif qualifier in ('APR', 'PR'):
            diagnosis_type = 'Patient Reason for Visit'
        elif qualifier in ('ABN', 'BN'):
            diagnosis_type = 'External Cause'
        
        codes.append({
            'type': diagnosis_type,
            'code': code,
            'qualifier': qualifier,
        })
    
    return codes


def _parse_amount(value: str) -> float:
    """Safely parse monetary amount."""
    if not value:
        return 0.0
    try:
        return float(value.replace('$', '').replace(',', ''))
    except (ValueError, AttributeError):
        return 0.0
