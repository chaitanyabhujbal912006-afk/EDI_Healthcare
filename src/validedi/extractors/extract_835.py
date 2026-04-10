"""
835 (Remittance Advice) data extractor.

Extracts payment and adjustment information from ERA files.
"""

from typing import Any


def extract_payments_835(parsed_edi) -> dict[str, Any]:
    """
    Extract structured payment data from 835 transaction.
    
    Returns dictionary with:
    - Payment summary (total amount, method, date)
    - Payer and payee information
    - Claim-level payment details
    - Service-level adjustments
    
    Args:
        parsed_edi: ParsedEDI object
        
    Returns:
        Dictionary with payment data
    """
    result = {
        'transaction_type': '835',
        'payment_summary': {},
        'payer': {},
        'payee': {},
        'claims': [],
    }
    
    # Extract payment summary from BPR segment
    for loop in parsed_edi.loops:
        bpr = loop.find_segment('BPR')
        if bpr:
            result['payment_summary'] = _extract_payment_summary(bpr)
            break
    
    # Extract payer information from 1000A loop
    for loop in parsed_edi.loops:
        if loop.loop_id == '1000A':
            result['payer'] = _extract_entity_info(loop)
            break
    
    # Extract payee information from 1000B loop
    for loop in parsed_edi.loops:
        if loop.loop_id == '1000B':
            result['payee'] = _extract_entity_info(loop)
            break
    
    # Extract claim payments from 2100 loops
    for loop in parsed_edi.loops:
        if loop.loop_id == '2000':  # Provider level
            for claim_loop in loop.children:
                if claim_loop.loop_id == '2100':
                    claim = _extract_claim_payment(claim_loop)
                    if claim:
                        result['claims'].append(claim)
    
    return result


def _extract_payment_summary(bpr_segment) -> dict[str, Any]:
    """Extract payment summary from BPR segment."""
    return {
        'total_amount': _parse_amount(bpr_segment.get_value(2)),
        'payment_method': bpr_segment.get_value(4),
        'payment_date': bpr_segment.get_value(16),
        'payer_account': bpr_segment.get_value(7),
        'payee_account': bpr_segment.get_value(13),
    }


def _extract_entity_info(entity_loop) -> dict[str, Any]:
    """Extract payer or payee information."""
    nm1 = entity_loop.find_segment('NM1')
    n3 = entity_loop.find_segment('N3')
    n4 = entity_loop.find_segment('N4')
    per = entity_loop.find_segment('PER')
    ref = entity_loop.find_segment('REF')
    
    entity = {}
    
    if nm1:
        entity['name'] = nm1.get_value(3)
        entity['npi'] = nm1.get_value(9)
    
    if n3:
        entity['address'] = n3.get_value(1)
    
    if n4:
        entity['city'] = n4.get_value(1)
        entity['state'] = n4.get_value(2)
        entity['zip'] = n4.get_value(3)
    
    if per:
        entity['contact'] = {
            'name': per.get_value(2),
            'phone': per.get_value(4),
        }
    
    if ref and ref.get_value(1) == 'EI':
        entity['tax_id'] = ref.get_value(2)
    
    return entity


def _extract_claim_payment(claim_loop) -> dict[str, Any] | None:
    """Extract claim payment information from 2100 loop."""
    clp = claim_loop.find_segment('CLP')
    if not clp:
        return None
    
    # Extract patient name from NM1
    patient_name = None
    nm1 = claim_loop.find_segment('NM1')
    if nm1 and nm1.get_value(1) == 'QC':  # Patient
        first = nm1.get_value(4)
        last = nm1.get_value(3)
        patient_name = f"{first} {last}" if first and last else (last or first)
    
    claim = {
        'patient_account': clp.get_value(1),
        'patient_name': patient_name,
        'claim_status_code': clp.get_value(2),
        'total_charged': _parse_amount(clp.get_value(3)),
        'total_paid': _parse_amount(clp.get_value(4)),
        'patient_responsibility': _parse_amount(clp.get_value(5)),
        'claim_number': clp.get_value(7),
        'services': [],
    }
    
    # Extract service-level details from 2110 loops
    for service_loop in claim_loop.children:
        if service_loop.loop_id == '2110':
            service = _extract_service_payment(service_loop)
            if service:
                claim['services'].append(service)
    
    return claim


def _extract_service_payment(service_loop) -> dict[str, Any] | None:
    """Extract service line payment information."""
    svc = service_loop.find_segment('SVC')
    if not svc:
        return None
    
    # Extract procedure code from SVC01 (composite)
    svc01 = svc.get(1)
    procedure_code = None
    if svc01.components:
        # Format: HC:99213 -> extract 99213
        procedure_code = svc01.components[-1] if svc01.components else svc01.raw
    else:
        procedure_code = svc01.raw
    
    service = {
        'procedure_code': procedure_code,
        'charged': _parse_amount(svc.get_value(2)),
        'paid': _parse_amount(svc.get_value(3)),
        'units': svc.get_value(5),
        'adjustments': [],
    }
    
    # Extract adjustment details from CAS segments
    cas_segments = service_loop.find_all('CAS')
    for cas in cas_segments:
        adjustment = _extract_adjustment(cas)
        if adjustment:
            service['adjustments'].append(adjustment)
    
    # Extract service date from DTM segment
    dtm = service_loop.find_segment('DTM')
    if dtm and dtm.get_value(1) == '472':
        service['service_date'] = dtm.get_value(2)
    
    return service


def _extract_adjustment(cas_segment) -> dict[str, Any] | None:
    """Extract adjustment information from CAS segment."""
    if not cas_segment:
        return None
    
    group_code = cas_segment.get_value(1)
    reason_code = cas_segment.get_value(2)
    amount = _parse_amount(cas_segment.get_value(3))
    
    # Map group codes to descriptions
    group_descriptions = {
        'CO': 'Contractual Obligation',
        'PR': 'Patient Responsibility',
        'PI': 'Payer Initiated Reduction',
        'OA': 'Other Adjustment',
    }
    
    return {
        'group': group_code,
        'group_description': group_descriptions.get(group_code, 'Unknown'),
        'reason_code': reason_code,
        'amount': amount,
    }


def _parse_amount(value: str) -> float:
    """Safely parse monetary amount."""
    if not value:
        return 0.0
    try:
        return float(value.replace('$', '').replace(',', ''))
    except (ValueError, AttributeError):
        return 0.0
