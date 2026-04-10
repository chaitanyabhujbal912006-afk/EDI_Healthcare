"""
834 (Benefit Enrollment) data extractor.

Extracts member enrollment and coverage information.
"""

from typing import Any


def extract_enrollments_834(parsed_edi) -> dict[str, Any]:
    """
    Extract structured enrollment data from 834 transaction.
    
    Returns dictionary with:
    - Transaction information
    - Sponsor/employer information
    - Insurer information
    - Member enrollment details with coverage
    
    Args:
        parsed_edi: ParsedEDI object
        
    Returns:
        Dictionary with enrollment data
    """
    result = {
        'transaction_type': '834',
        'transaction_info': {},
        'sponsor': {},
        'insurer': {},
        'members': [],
    }
    
    # Extract transaction info from BGN segment
    for loop in parsed_edi.loops:
        bgn = loop.find_segment('BGN')
        if bgn:
            result['transaction_info'] = _extract_transaction_info(bgn)
            break
    
    # Extract sponsor information from 1000A loop
    for loop in parsed_edi.loops:
        if loop.loop_id == '1000A':
            result['sponsor'] = _extract_sponsor_info(loop)
            break
    
    # Extract insurer information from 1000B loop
    for loop in parsed_edi.loops:
        if loop.loop_id == '1000B':
            result['insurer'] = _extract_insurer_info(loop)
            break
    
    # Extract member enrollments from 2000 loops
    for loop in parsed_edi.loops:
        if loop.loop_id == '2000':
            member = _extract_member_enrollment(loop)
            if member:
                result['members'].append(member)
    
    return result


def _extract_transaction_info(bgn_segment) -> dict[str, Any]:
    """Extract transaction information from BGN segment."""
    return {
        'purpose': bgn_segment.get_value(1),
        'reference_id': bgn_segment.get_value(2),
        'date': bgn_segment.get_value(3),
        'time': bgn_segment.get_value(4),
    }


def _extract_sponsor_info(sponsor_loop) -> dict[str, Any]:
    """Extract sponsor/employer information."""
    n1 = sponsor_loop.find_segment('N1')
    ref = sponsor_loop.find_segment('REF')
    
    sponsor = {}
    
    if n1:
        sponsor['name'] = n1.get_value(2)
    
    if ref:
        ref_qualifier = ref.get_value(1)
        if ref_qualifier == '0F':  # Master policy number
            sponsor['master_policy'] = ref.get_value(2)
        elif ref_qualifier == 'EI':  # Tax ID
            sponsor['tax_id'] = ref.get_value(2)
    
    return sponsor


def _extract_insurer_info(insurer_loop) -> dict[str, Any]:
    """Extract insurer/carrier information."""
    n1 = insurer_loop.find_segment('N1')
    ref = insurer_loop.find_segment('REF')
    
    insurer = {}
    
    if n1:
        insurer['name'] = n1.get_value(2)
    
    if ref and ref.get_value(1) == 'EI':
        insurer['tax_id'] = ref.get_value(2)
    
    return insurer


def _extract_member_enrollment(member_loop) -> dict[str, Any] | None:
    """Extract member enrollment information from 2000 loop."""
    ins = member_loop.find_segment('INS')
    if not ins:
        return None
    
    # Map relationship codes to descriptions
    relationship_map = {
        '01': 'Spouse',
        '18': 'Self',
        '19': 'Child',
        '20': 'Employee',
        '21': 'Unknown',
        '29': 'Significant Other',
        '32': 'Mother',
        '33': 'Father',
        '34': 'Other Adult',
        '53': 'Life Partner',
        'G8': 'Other Relationship',
    }
    
    relationship_code = ins.get_value(2)
    
    member = {
        'is_subscriber': ins.get_value(1) == 'Y',
        'relationship': relationship_map.get(relationship_code, relationship_code),
        'relationship_code': relationship_code,
        'maintenance_type': ins.get_value(3),
        'benefit_status': ins.get_value(4),
        'demographics': {},
        'coverage': {},
    }
    
    # Extract demographics from NM1 and DMG segments
    nm1 = member_loop.find_segment('NM1')
    if nm1:
        member['demographics']['first_name'] = nm1.get_value(4)
        member['demographics']['last_name'] = nm1.get_value(3)
        member['demographics']['member_id'] = nm1.get_value(9)
    
    dmg = member_loop.find_segment('DMG')
    if dmg:
        member['demographics']['dob'] = dmg.get_value(2)
        gender_code = dmg.get_value(3)
        member['demographics']['gender'] = 'Male' if gender_code == 'M' else 'Female' if gender_code == 'F' else gender_code
    
    # Extract address from N3 and N4 segments
    n3 = member_loop.find_segment('N3')
    n4 = member_loop.find_segment('N4')
    
    if n3 or n4:
        address = {}
        if n3:
            address['street'] = n3.get_value(1)
            address['suite'] = n3.get_value(2)
        if n4:
            address['city'] = n4.get_value(1)
            address['state'] = n4.get_value(2)
            address['zip'] = n4.get_value(3)
        member['demographics']['address'] = address
    
    # Extract phone from PER segment
    per = member_loop.find_segment('PER')
    if per:
        member['demographics']['phone'] = per.get_value(4)
    
    # Extract SSN from REF segment
    ref_segments = member_loop.find_all('REF')
    for ref in ref_segments:
        if ref.get_value(1) == '0F':  # Subscriber number
            member['subscriber_number'] = ref.get_value(2)
        elif ref.get_value(1) == 'SY':  # SSN
            member['demographics']['ssn'] = ref.get_value(2)
    
    # Extract coverage information from 2300 loops
    for coverage_loop in member_loop.children:
        if coverage_loop.loop_id == '2300':
            coverage = _extract_coverage_info(coverage_loop)
            if coverage:
                member['coverage'] = coverage
                break  # Take first coverage for simplicity
    
    return member


def _extract_coverage_info(coverage_loop) -> dict[str, Any]:
    """Extract coverage information from 2300 loop."""
    hd = coverage_loop.find_segment('HD')
    dtp_segments = coverage_loop.find_all('DTP')
    ref = coverage_loop.find_segment('REF')
    
    coverage = {}
    
    if hd:
        coverage['maintenance_type'] = hd.get_value(1)
        coverage['insurance_line_code'] = hd.get_value(3)
    
    # Extract coverage dates
    for dtp in dtp_segments:
        qualifier = dtp.get_value(1)
        date_value = dtp.get_value(3)
        
        if qualifier == '348':  # Benefit begin
            coverage['benefit_begin'] = date_value
        elif qualifier == '349':  # Benefit end
            coverage['benefit_end'] = date_value
    
    # Extract group policy number
    if ref and ref.get_value(1) == '1L':
        coverage['group_policy'] = ref.get_value(2)
    
    return coverage
