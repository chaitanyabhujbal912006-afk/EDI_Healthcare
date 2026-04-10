"""
Duplicate member ID detection for 834 transactions.
"""

from validedi.engine.models import Loop, ValidationError


def duplicate_member_check(transaction_loops: list[Loop]) -> list[ValidationError]:
    """
    Check for duplicate member IDs within a transaction.
    
    Args:
        transaction_loops: All top-level loops in the transaction
        
    Returns:
        List of validation errors for duplicates found
    """
    errors = []
    seen_ids: dict[str, int] = {}  # member_id -> first position
    
    # Find all 2000 member loops
    for loop in transaction_loops:
        if loop.loop_id == '2000':
            # Find REF segment with member ID
            ref_segment = loop.find_segment('REF')
            if ref_segment:
                # REF02 typically contains the member ID
                member_id = ref_segment.get_value(2)
                
                if member_id:
                    if member_id in seen_ids:
                        # Duplicate found
                        errors.append(ValidationError(
                            code='DUPLICATE_MEMBER_CHECK',
                            severity='error',
                            segment='REF',
                            element='REF02',
                            loop='2000',
                            position=ref_segment.position,
                            message=f'Duplicate member ID {member_id} found (first occurrence at position {seen_ids[member_id]})'
                        ))
                    else:
                        seen_ids[member_id] = ref_segment.position
    
    return errors
