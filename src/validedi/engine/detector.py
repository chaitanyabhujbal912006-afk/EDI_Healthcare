"""
EDI delimiter and transaction type detector.
"""

from dataclasses import dataclass
from validedi.utils.exceptions import EDIParseError, UnsupportedTransactionError


@dataclass
class DelimiterSet:
    """Detected delimiters from ISA segment."""
    element_sep: str
    segment_sep: str
    sub_sep: str
    transaction_type: str


def detect(raw: str) -> DelimiterSet:
    """
    Detect delimiters and transaction type from raw EDI string.
    
    Args:
        raw: Raw EDI string
        
    Returns:
        DelimiterSet with detected delimiters and transaction type
        
    Raises:
        EDIParseError: If ISA segment is malformed or too short
        UnsupportedTransactionError: If transaction type is not recognized
    """
    if len(raw) < 106:
        raise EDIParseError(
            'ISA segment too short — not valid X12',
            raw_preview=raw
        )
    
    # Extract delimiters from ISA segment
    element_sep = raw[3]  # 4th character (index 3)
    
    # The segment separator is right after the ISA segment (106 chars)
    # It should be at position 105 or 106 depending on ISA structure
    segment_sep = raw[105] if raw[105] in ('~', '\n', '\r') else raw[106] if len(raw) > 106 else '~'
    
    # Split ISA by element separator to get ISA16 (sub-element separator)
    isa_elements = raw[:106].split(element_sep)
    if len(isa_elements) < 17:
        raise EDIParseError(
            f'ISA segment does not have 16 elements (found {len(isa_elements) - 1})',
            raw_preview=raw
        )
    
    # ISA16 is the sub-element separator (single character)
    # Strip any trailing segment separator
    sub_sep_raw = isa_elements[16] if len(isa_elements) > 16 else ':'
    sub_sep = sub_sep_raw[0] if sub_sep_raw else ':'
    
    # Find GS and ST segments to determine transaction type
    segments = raw.split(segment_sep)
    
    gs_code = None
    st_code = None
    
    for segment in segments:
        if not segment.strip():
            continue
            
        elements = segment.split(element_sep)
        seg_id = elements[0].strip()
        
        if seg_id == 'GS' and len(elements) > 1:
            gs_code = elements[1].strip()
        elif seg_id == 'ST' and len(elements) > 1:
            st_code = elements[1].strip()
            break
    
    if not gs_code or not st_code:
        raise EDIParseError(
            'Could not find GS or ST segments',
            raw_preview=raw
        )
    
    # Map GS/ST codes to transaction type
    transaction_type = _determine_transaction_type(gs_code, st_code, raw, element_sep)
    
    return DelimiterSet(
        element_sep=element_sep,
        segment_sep=segment_sep,
        sub_sep=sub_sep,
        transaction_type=transaction_type
    )



def _determine_transaction_type(gs_code: str, st_code: str, raw: str, element_sep: str) -> str:
    """
    Determine transaction type from GS and ST codes.
    
    For 837 transactions, check ST03 (implementation guide version) first,
    then fall back to CLM05-02 if needed.
    """
    # Map known transaction types
    if gs_code == 'HC' and st_code == '837':
        # Need to distinguish 837P from 837I
        # Method 1: Check ST03 (implementation guide version) - most reliable
        segments = raw.split('~')
        for segment in segments:
            if segment.strip().startswith('ST' + element_sep):
                elements = segment.split(element_sep)
                if len(elements) > 3:
                    version = elements[3].strip()
                    # 837I uses 005010X223A2, 837P uses 005010X222A1
                    if '005010X223' in version:
                        return '837i'
                    elif '005010X222' in version:
                        return '837p'
                break
        
        # Method 2: Fallback - check CLM05-02
        for segment in segments:
            if segment.strip().startswith('CLM' + element_sep):
                elements = segment.split(element_sep)
                if len(elements) > 5:
                    # CLM05 is a composite, check second component
                    clm05 = elements[5]
                    if ':' in clm05:
                        clm05_components = clm05.split(':')
                        if len(clm05_components) > 1:
                            clm05_02 = clm05_components[1]
                            if clm05_02 == 'I':
                                return '837i'
                            elif clm05_02 == 'P':
                                return '837p'
                # If CLM05-02 is empty or not 'I', assume professional
                return '837p'
        
        # Default to 837P if can't determine
        return '837p'
    
    elif gs_code == 'HP' and st_code == '835':
        return '835'
    
    elif gs_code == 'HP':
        # GS says 835 but ST might be wrong — return 835 and let validator flag ST mismatch
        return '835'
    
    elif gs_code == 'BE' and st_code == '834':
        return '834'
    
    elif gs_code == 'BE':
        # GS says 834 but ST might be wrong
        return '834'
    
    else:
        raise UnsupportedTransactionError(
            f'Unsupported transaction type: GS={gs_code}, ST={st_code}',
            transaction_type_detected=f'{gs_code}_{st_code}'
        )
