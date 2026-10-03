"""
Duplicate member ID detection for 834 transactions.
"""

from validedi.engine.models import Loop, ValidationError


def duplicate_member_check(transaction_loops: list[Loop]) -> list[ValidationError]:
    """
    Check for duplicate member IDs within a transaction across all 2000 member loops.
    Checks REF (0F, 1L, SY, 23) and NM1*IL member identifiers.
    """
    errors = []
    seen_ids: dict[str, int] = {}  # member_id -> first position

    # Recursively find all 2000 member loops
    member_loops: list[Loop] = []
    def _find_2000(lp: Loop):
        if lp.loop_id == '2000':
            member_loops.append(lp)
        for ch in lp.children:
            _find_2000(ch)

    for lp in transaction_loops:
        _find_2000(lp)

    for loop in member_loops:
        member_id = None
        pos = 0
        seg_name = 'REF'
        elem_name = 'REF02'

        # Look for REF segment
        for seg in loop.segments:
            if seg.segment_id == 'REF':
                val = seg.get_value(2).strip()
                if val:
                    member_id = val
                    pos = seg.position
                    seg_name = 'REF'
                    elem_name = 'REF02'
                    break

        # Fallback to NM1*IL element 9 (member ID)
        if not member_id:
            for seg in loop.segments:
                if seg.segment_id == 'NM1' and seg.get_value(1) == 'IL':
                    val = seg.get_value(9).strip()
                    if val:
                        member_id = val
                        pos = seg.position
                        seg_name = 'NM1'
                        elem_name = 'NM109'
                        break

        # Check child loops if NM1 is inside 2100 child loop
        if not member_id:
            for child in loop.children:
                nm1 = child.find_segment('NM1')
                if nm1 and nm1.get_value(1) == 'IL':
                    val = nm1.get_value(9).strip()
                    if val:
                        member_id = val
                        pos = nm1.position
                        seg_name = 'NM1'
                        elem_name = 'NM109'
                        break

        if member_id:
            if member_id in seen_ids:
                errors.append(ValidationError(
                    code='MEMBER_DUPLICATE',
                    severity='error',
                    segment=seg_name,
                    element=elem_name,
                    loop='2000',
                    position=pos,
                    message=f'Duplicate subscriber/member identifier {member_id} found in file.'
                ))
            else:
                seen_ids[member_id] = pos

    return errors

