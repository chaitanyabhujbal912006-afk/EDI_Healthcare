"""
835 remittance-specific validation handlers.
"""

from validedi.engine.models import Loop, ValidationError


def bpr_clp_total_match(loops: list[Loop]) -> list[ValidationError]:
    """
    Verify BPR02 (total payment) equals sum of all CLP04 (claim paid amounts) minus
    PLB provider-level adjustments: BPR02 == sum(CLP04) - sum(PLB adjustments).
    """
    errors = []

    all_segs = []
    def _collect(lp: Loop):
        all_segs.extend(lp.segments)
        for ch in lp.children:
            _collect(ch)

    if isinstance(loops, list):
        for lp in loops:
            _collect(lp)
    elif hasattr(loops, 'segments'):
        _collect(loops)

    bpr_seg = next((s for s in all_segs if s.segment_id == 'BPR'), None)
    if not bpr_seg:
        return errors  # Missing BPR caught by required_segment rule

    try:
        bpr_total = float(bpr_seg.get_value(2))
    except (ValueError, TypeError):
        return errors

    # Sum CLP04 across all CLP segments
    clp_total = 0.0
    for seg in all_segs:
        if seg.segment_id == 'CLP':
            try:
                clp_total += float(seg.get_value(4))
            except (ValueError, TypeError):
                pass

    # Sum PLB provider-level adjustments
    # PLB has pairs of reason/amount at elements (3,4), (5,6), (7,8), (9,10), (11,12), (13,14)
    plb_total = 0.0
    for seg in all_segs:
        if seg.segment_id == 'PLB':
            for elem_idx in range(4, 15, 2):
                val = seg.get_value(elem_idx).strip()
                if val:
                    try:
                        plb_total += float(val)
                    except (ValueError, TypeError):
                        pass

    expected_bpr = clp_total - plb_total
    if abs(bpr_total - expected_bpr) > 0.01:
        errors.append(ValidationError(
            code='835-007',
            severity='warning',
            segment='BPR',
            element='BPR02',
            loop='HEADER',
            position=bpr_seg.position,
            message=(
                f'BPR02 total payment (${bpr_total:.2f}) does not match '
                f'expected amount (${expected_bpr:.2f}) based on sum of CLP04 (${clp_total:.2f}) '
                f'minus PLB adjustments (${plb_total:.2f}).'
            )
        ))
    return errors



def duplicate_bht_check(loops: list[Loop]) -> list[ValidationError]:
    """
    Verify only one BHT segment exists per transaction set (837I requirement).
    """
    errors = []
    bht_count = 0
    for loop in loops:
        bht_count += len(loop.find_all('BHT'))
        for child in loop.children:
            bht_count += len(child.find_all('BHT'))

    if bht_count > 1:
        errors.append(ValidationError(
            code='837-015',
            severity='error',
            segment='BHT',
            element=None,
            loop='HEADER',
            position=0,
            message=f'Duplicate BHT segment: found {bht_count}, expected exactly 1 per transaction set'
        ))
    return errors


def cas_balance_check(loops: list[Loop]) -> list[ValidationError]:
    """
    For each CLP, verify: CLP03 (charged) == CLP04 (paid) + sum(CAS adjustment amounts).
    """
    errors: list[ValidationError] = []

    def check_loop(loop: Loop) -> None:
        for child in loop.children:
            clp = child.find_segment('CLP')
            if not clp:
                check_loop(child)
                continue

            try:
                charged = float(clp.get_value(3))
                paid = float(clp.get_value(4))
            except (ValueError, TypeError):
                check_loop(child)
                continue

            # Sum all CAS adjustment amounts in this CLP loop (claim-level and service-level)
            cas_total = 0.0
            def sum_cas_in_segs(segments):
                total = 0.0
                for seg in segments:
                    if seg.segment_id == 'CAS':
                        for amt_idx in range(3, 19, 3):
                            try:
                                total += float(seg.get_value(amt_idx))
                            except (ValueError, TypeError):
                                pass
                return total

            cas_total += sum_cas_in_segs(child.segments)
            for grandchild in child.children:
                cas_total += sum_cas_in_segs(grandchild.segments)

            expected_charged = paid + cas_total
            if abs(expected_charged - charged) > 0.01:
                errors.append(ValidationError(
                    code='835-010',
                    severity='warning',
                    segment='CLP',
                    element='CLP03',
                    loop=child.loop_id,
                    position=clp.position,
                    message=(
                        f'CAS balance mismatch for claim {clp.get_value(1)}: '
                        f'charged=${charged:.2f}, paid=${paid:.2f}, '
                        f'adjustments=${cas_total:.2f}, '
                        f'paid+adj=${expected_charged:.2f} ≠ charged'
                    ),
                ))
            check_loop(child)

    for loop in loops:
        check_loop(loop)
    return errors


def missing_svc_check(loops: list[Loop]) -> list[ValidationError]:
    """
    Flag CLP loops that have no SVC (service line) segments.
    """
    errors: list[ValidationError] = []

    def check_loop(loop: Loop) -> None:
        for child in loop.children:
            clp = child.find_segment('CLP')
            if clp:
                # Check for SVC in this CLP's children
                has_svc = any(
                    grandchild.find_segment('SVC')
                    for grandchild in child.children
                )
                # Also check direct segments
                if not has_svc:
                    has_svc = child.find_segment('SVC') is not None
                if not has_svc:
                    errors.append(ValidationError(
                        code='835-011',
                        severity='warning',
                        segment='CLP',
                        element='CLP01',
                        loop=child.loop_id,
                        position=clp.position,
                        message=f'CLP {clp.get_value(1)} has no SVC service line segments',
                    ))
            check_loop(child)

    for loop in loops:
        check_loop(loop)
    return errors


def plb_orphan_check(loops: list[Loop]) -> list[ValidationError]:
    """
    Check that PLB adjustment claim references exist in CLP01 values.
    """
    errors: list[ValidationError] = []

    # Collect all CLP01 claim numbers
    clp_ids: set[str] = set()

    def collect_clp(loop: Loop) -> None:
        for child in loop.children:
            clp = child.find_segment('CLP')
            if clp:
                clp_id = clp.get_value(1).strip()
                if clp_id:
                    clp_ids.add(clp_id)
            collect_clp(child)

    for loop in loops:
        collect_clp(loop)

    # Check PLB references
    def check_plb(loop: Loop) -> None:
        for seg in loop.segments:
            if seg.segment_id == 'PLB':
                # PLB04, PLB06, PLB08, PLB10, PLB12 are claim references
                for ref_idx in range(4, 13, 2):
                    ref = seg.get_value(ref_idx).strip()
                    if ref and ref not in clp_ids:
                        errors.append(ValidationError(
                            code='835-012',
                            severity='warning',
                            segment='PLB',
                            element=f'PLB{ref_idx:02d}',
                            loop=loop.loop_id,
                            position=seg.position,
                            message=f'PLB adjustment references claim {ref!r} '
                                    f'which does not appear in any CLP01 in this file',
                        ))
        for child in loop.children:
            check_plb(child)

    for loop in loops:
        check_plb(loop)
    return errors
