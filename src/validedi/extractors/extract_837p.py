"""
837P (Professional Claims) data extractor.

Extracts structured claim data matching business requirements.
"""

from typing import Any


def extract_claims_837p(parsed_edi) -> list[dict[str, Any]]:
    """
    Extract structured claim data from 837P transaction.
    
    Returns list of claims with:
    - Claim ID, totals, dates
    - Patient demographics
    - Provider information
    - Diagnosis codes
    - Service lines with procedures and charges
    
    Args:
        parsed_edi: ParsedEDI object
        
    Returns:
        List of claim dictionaries
    """
    claims = []
    
    # Navigate loop hierarchy: 2000A -> 2000B -> 2300 (claims)
    for billing_loop in parsed_edi.loops:
        if billing_loop.loop_id == '2000A':
            # Extract billing provider info
            billing_provider = _extract_provider_info(billing_loop)
            
            for subscriber_loop in billing_loop.children:
                if subscriber_loop.loop_id == '2000B':
                    # Extract subscriber/patient info
                    subscriber = _extract_subscriber_info(subscriber_loop)
                    
                    for claim_loop in subscriber_loop.children:
                        if claim_loop.loop_id == '2300':
                            claim = _extract_claim_837p(claim_loop)
                            claim['billing_provider'] = billing_provider
                            claim['patient'] = subscriber
                            claims.append(claim)
    
    return claims


def _extract_claim_837p(claim_loop) -> dict[str, Any]:
    """Extract data from a 2300 claim loop."""
    clm = claim_loop.find_segment('CLM')
    hi = claim_loop.find_segment('HI')
    
    claim = {
        'claim_id': clm.get_value(1) if clm else None,
        'total_charge': _parse_amount(clm.get_value(2)) if clm else 0.0,
        'place_of_service': None,
        'claim_frequency': None,
        'diagnoses': [],
        'service_lines': [],
    }
    
    # Extract place of service from CLM05
    if clm:
        clm05 = clm.get(5)
        if clm05.components:
            claim['place_of_service'] = clm05.get(1)
            claim['claim_frequency'] = clm05.get(3) if len(clm05.components) >= 3 else None
    
    # Extract diagnosis codes from HI segment
    if hi:
        claim['diagnoses'] = _extract_diagnosis_codes(hi)
    
    # Extract service lines from 2400 loops
    for service_loop in claim_loop.children:
        if service_loop.loop_id == '2400':
            service_line = _extract_service_line_837p(service_loop)
            if service_line:
                claim['service_lines'].append(service_line)
    
    return claim


def _extract_service_line_837p(service_loop) -> dict[str, Any] | None:
    """Extract data from a 2400 service line loop."""
    sv1 = service_loop.find_segment('SV1')
    if not sv1:
        return None
    
    # Extract procedure code from SV101 (composite)
    sv101 = sv1.get(1)
    procedure_code = None
    if sv101.components:
        # Format: HC:99213 -> extract 99213
        procedure_code = sv101.components[-1] if sv101.components else sv101.raw
    else:
        procedure_code = sv101.raw
    
    # Extract charge from SV102 (composite: charge*unit*quantity)
    sv102 = sv1.get(2)
    charge = 0.0
    if sv102.components:
        charge = _parse_amount(sv102.components[0])
    else:
        charge = _parse_amount(sv102.raw)
    
    # Extract units from SV104
    units = sv1.get_value(4)
    
    # Extract service date from DTP segment
    service_date = None
    dtp = service_loop.find_segment('DTP')
    if dtp and dtp.get_value(1) == '472':  # Service date qualifier
        service_date = dtp.get_value(3)
    
    return {
        'procedure_code': procedure_code,
        'charge': charge,
        'units': units,
        'service_date': service_date,
    }


def _extract_provider_info(provider_loop) -> dict[str, Any]:
    """Extract provider information from loop."""
    nm1 = provider_loop.find_segment('NM1')
    n3 = provider_loop.find_segment('N3')
    n4 = provider_loop.find_segment('N4')
    ref = provider_loop.find_segment('REF')
    
    provider = {}
    
    if nm1:
        provider['name'] = nm1.get_value(3)
        provider['npi'] = nm1.get_value(9)
    
    if n3:
        provider['address'] = n3.get_value(1)
    
    if n4:
        provider['city'] = n4.get_value(1)
        provider['state'] = n4.get_value(2)
        provider['zip'] = n4.get_value(3)
    
    if ref and ref.get_value(1) == 'EI':
        provider['tax_id'] = ref.get_value(2)
    
    return provider


def _extract_subscriber_info(subscriber_loop) -> dict[str, Any]:
    """Extract subscriber/patient information."""
    nm1 = subscriber_loop.find_segment('NM1')
    dmg = subscriber_loop.find_segment('DMG')
    n3 = subscriber_loop.find_segment('N3')
    n4 = subscriber_loop.find_segment('N4')
    
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
    
    return patient


def _extract_diagnosis_codes(hi_segment) -> list[dict[str, str]]:
    """Extract diagnosis codes from HI segment."""
    codes = []
    
    # HI can have up to 12 diagnosis codes (HI01-HI12)
    for i in range(1, 13):
        element = hi_segment.get(i)
        if not element.raw:
            continue
        
        # Format: ABK:I10 -> extract qualifier and code
        qualifier = None
        code = element.raw
        
        if ':' in element.raw:
            parts = element.raw.split(':', 1)
            qualifier = parts[0]
            code = parts[1] if len(parts) > 1 else code
        
        # Determine diagnosis type from qualifier
        diagnosis_type = 'Additional'
        if i == 1 or qualifier == 'ABK':
            diagnosis_type = 'Primary'
        elif qualifier == 'APR':
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
