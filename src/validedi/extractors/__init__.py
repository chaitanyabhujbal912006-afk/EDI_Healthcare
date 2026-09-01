"""
Data extraction helpers for converting parsed EDI into structured business data.

These extractors transform hierarchical loop structures into JSON-serializable
dictionaries matching common business requirements.
"""

from validedi.extractors.extract_837p import extract_claims_837p
from validedi.extractors.extract_837i import extract_claims_837i
from validedi.extractors.extract_835 import extract_payments_835
from validedi.extractors.extract_834 import extract_enrollments_834


def extract_claims(parsed_edi):
    """
    Extract claim data from 837P or 837I transaction.
    
    Args:
        parsed_edi: ParsedEDI object
        
    Returns:
        List of claim dictionaries with structured data
        
    Raises:
        ValueError: If transaction type is not 837P or 837I
    """
    tx_type = (parsed_edi.envelope.transaction_type or '').lower()
    
    if tx_type in ('837p', '837'):
        return extract_claims_837p(parsed_edi)
    elif tx_type == '837i':
        return extract_claims_837i(parsed_edi)
    else:
        raise ValueError(f"extract_claims() only supports 837P and 837I, got {tx_type}")


def extract_payments(parsed_edi):
    """
    Extract payment data from 835 remittance transaction.
    
    Args:
        parsed_edi: ParsedEDI object
        
    Returns:
        Dictionary with payment summary and claim details
        
    Raises:
        ValueError: If transaction type is not 835
    """
    tx_type = (parsed_edi.envelope.transaction_type or '').lower()
    if tx_type != '835':
        raise ValueError(f"extract_payments() only supports 835, got {tx_type}")
    
    return extract_payments_835(parsed_edi)


def extract_enrollments(parsed_edi):
    """
    Extract enrollment data from 834 benefit enrollment transaction.
    
    Args:
        parsed_edi: ParsedEDI object
        
    Returns:
        Dictionary with enrollment summary and member details
        
    Raises:
        ValueError: If transaction type is not 834
    """
    tx_type = (parsed_edi.envelope.transaction_type or '').lower()
    if tx_type != '834':
        raise ValueError(f"extract_enrollments() only supports 834, got {tx_type}")
    
    return extract_enrollments_834(parsed_edi)


__all__ = [
    'extract_claims',
    'extract_payments',
    'extract_enrollments',
    'extract_claims_837p',
    'extract_claims_837i',
    'extract_payments_835',
    'extract_enrollments_834',
]
