"""
JSON export functionality for parsed EDI data.
"""

import json
from typing import Any
from validedi.extractors import extract_claims, extract_payments, extract_enrollments


def export_json(parsed_edi, validation_result=None, include_raw=False) -> dict[str, Any]:
    """
    Export parsed EDI data to JSON-serializable dictionary.
    
    Args:
        parsed_edi: ParsedEDI object
        validation_result: Optional ValidationResult object
        include_raw: Whether to include raw EDI content
        
    Returns:
        Dictionary with structured data (JSON-serializable)
    """
    tx_type = parsed_edi.envelope.transaction_type
    
    # Build base structure
    output = {
        'transaction_type': tx_type,
        'envelope': {
            'sender_id': parsed_edi.envelope.sender_id,
            'receiver_id': parsed_edi.envelope.receiver_id,
            'interchange_date': parsed_edi.envelope.interchange_date,
            'interchange_time': parsed_edi.envelope.interchange_time,
            'version': parsed_edi.envelope.version,
            'isa_control_number': parsed_edi.envelope.isa_control_number,
            'gs_control_number': parsed_edi.envelope.gs_control_number,
            'st_control_number': parsed_edi.envelope.st_control_number,
        },
    }
    
    # Add validation results if provided
    if validation_result:
        output['validation'] = {
            'is_valid': validation_result.is_valid,
            'error_count': validation_result.error_count,
            'warning_count': validation_result.warning_count,
            'errors': [
                {
                    'code': err.code,
                    'severity': err.severity,
                    'segment': err.segment,
                    'element': err.element,
                    'loop': err.loop,
                    'message': err.message,
                }
                for err in validation_result.errors
            ],
        }
    
    # Extract business data based on transaction type
    try:
        if tx_type in ('837p', '837i'):
            output['claims'] = extract_claims(parsed_edi)
        elif tx_type == '835':
            payment_data = extract_payments(parsed_edi)
            output.update(payment_data)
        elif tx_type == '834':
            enrollment_data = extract_enrollments(parsed_edi)
            output.update(enrollment_data)
    except Exception as e:
        # If extraction fails, include error but don't fail export
        output['extraction_error'] = str(e)
    
    # Optionally include raw EDI
    if include_raw:
        output['raw_edi'] = parsed_edi.raw_content
    
    return output


def export_json_to_file(parsed_edi, filepath: str, validation_result=None, include_raw=False, indent=2):
    """
    Export parsed EDI data to JSON file.
    
    Args:
        parsed_edi: ParsedEDI object
        filepath: Output file path
        validation_result: Optional ValidationResult object
        include_raw: Whether to include raw EDI content
        indent: JSON indentation level (None for compact)
    """
    output = export_json(parsed_edi, validation_result, include_raw)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=indent, default=str)
