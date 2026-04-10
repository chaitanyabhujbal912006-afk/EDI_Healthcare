"""
Claim-level validation handlers for 837P and 837I transactions.
"""

from validedi.engine.models import Loop, ValidationError

# Valid CLM05-3 claim frequency codes
VALID_FREQUENCY_CODES = {'1', '2', '3', '4', '5', '6', '7', '8', '9'}
STANDARD_FREQUENCY_CODES = {'1', '7', '8'}  # original, replacement, void

# Valid UB-04 admission type codes
VALID_ADMISSION_TYPES = {'1', '2', '3', '4', '5', '9'}
# Valid UB-04 admission source codes
VALID_ADMISSION_SOURCES = {'1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D'}


def clm_frequency_code_check(loops: list[Loop]) -> list[ValidationError]:
    """
    Validate CLM05-3 (claim frequency code) is a recognized value.
    CLM05 is a composite: place_of_service:facility_type:frequency_code
    """
    errors: list[ValidationError] = []
    for loop in loops:
        errors.extend(_check_clm_freq_in_loop(loop))
    return errors


def _check_clm_freq_in_loop(loop: Loop) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for seg in loop.segments:
        if seg.segment_id == 'CLM':
            clm05 = seg.get(5)
            # CLM05 is composite: components[0]=POS, [1]=facility_type, [2]=freq_code
            if clm05.components and len(clm05.components) >= 3:
                freq_code = clm05.components[2].strip()
            elif clm05.raw and '*' not in clm05.raw:
                # Might be stored as raw with colons
                parts = clm05.raw.split(':')
                freq_code = parts[2].strip() if len(parts) >= 3 else ''
            else:
                freq_code = ''

            if freq_code and freq_code not in VALID_FREQUENCY_CODES:
                errors.append(ValidationError(
                    code='837-017',
                    severity='warning',
                    segment='CLM',
                    element='CLM05',
                    loop=loop.loop_id,
                    position=seg.position,
                    message=f'CLM05-3 frequency code {freq_code!r} is not a valid value. '
                            f'Expected: 1=Original, 7=Replacement, 8=Void',
                ))
    for child in loop.children:
        errors.extend(_check_clm_freq_in_loop(child))
    return errors


def all_zero_charges_check(loops: list[Loop]) -> list[ValidationError]:
    """
    Check if all service line charges across the entire transaction are $0.00.
    """
    sv1_charges: list[float] = []
    sv2_charges: list[float] = []

    def collect(loop: Loop) -> None:
        for seg in loop.segments:
            if seg.segment_id == 'SV1':
                try:
                    sv1_charges.append(float(seg.get_value(2)))
                except ValueError:
                    pass
            elif seg.segment_id == 'SV2':
                try:
                    sv2_charges.append(float(seg.get_value(3)))
                except ValueError:
                    pass
        for child in loop.children:
            collect(child)

    for loop in loops:
        collect(loop)

    all_charges = sv1_charges + sv2_charges
    if all_charges and all(c == 0.0 for c in all_charges):
        return [ValidationError(
            code='837-018',
            severity='warning',
            segment='SV1',
            element='SV102',
            loop=None,
            position=0,
            message=f'All {len(all_charges)} service line charge(s) are $0.00 — '
                    'zero-dollar claims are rejected by most payers',
        )]
    return []


def admission_type_check(loops: list[Loop]) -> list[ValidationError]:
    """
    Validate CLM11-1 (admission type) and CLM11-2 (admission source) for 837I.
    CLM11 is a composite element.
    """
    errors: list[ValidationError] = []

    def check_loop(loop: Loop) -> None:
        for seg in loop.segments:
            if seg.segment_id == 'CLM':
                clm11 = seg.get(11)
                if clm11.components:
                    adm_type = clm11.components[0].strip() if len(clm11.components) > 0 else ''
                    adm_src = clm11.components[1].strip() if len(clm11.components) > 1 else ''
                else:
                    parts = clm11.raw.split(':') if clm11.raw else []
                    adm_type = parts[0].strip() if len(parts) > 0 else ''
                    adm_src = parts[1].strip() if len(parts) > 1 else ''

                if adm_type and adm_type not in VALID_ADMISSION_TYPES:
                    errors.append(ValidationError(
                        code='837I-ADMISSION-TYPE',
                        severity='warning',
                        segment='CLM',
                        element='CLM11',
                        loop=loop.loop_id,
                        position=seg.position,
                        message=f'CLM11-1 admission type {adm_type!r} is not a valid UB-04 code. '
                                f'Valid values: 1=Emergency, 2=Urgent, 3=Elective, 4=Newborn, 5=Trauma',
                    ))
                if adm_src and adm_src not in VALID_ADMISSION_SOURCES:
                    errors.append(ValidationError(
                        code='837I-ADMISSION-TYPE',
                        severity='warning',
                        segment='CLM',
                        element='CLM11',
                        loop=loop.loop_id,
                        position=seg.position,
                        message=f'CLM11-2 admission source {adm_src!r} is not a valid UB-04 code',
                    ))
        for child in loop.children:
            check_loop(child)

    for loop in loops:
        check_loop(loop)
    return errors


def drg_code_check(loops: list[Loop]) -> list[ValidationError]:
    """
    Check that inpatient 837I claims have a DRG code (HI*DR) in the 2300 loop.
    Only flags if the claim appears to be inpatient (CLM05-1 = 21 or CLM05-2 = 1).
    """
    errors: list[ValidationError] = []

    def check_loop(loop: Loop) -> None:
        clm_seg = None
        hi_segs = []
        for seg in loop.segments:
            if seg.segment_id == 'CLM':
                clm_seg = seg
            elif seg.segment_id == 'HI':
                hi_segs.append(seg)

        if clm_seg and hi_segs:
            # Check if inpatient: CLM05-1 = 21 (inpatient hospital)
            clm05 = clm_seg.get(5)
            if clm05.components:
                pos_code = clm05.components[0].strip()
            else:
                parts = clm05.raw.split(':') if clm05.raw else []
                pos_code = parts[0].strip() if parts else ''

            is_inpatient = pos_code == '21'
            if is_inpatient:
                # Look for DRG qualifier in any HI segment
                has_drg = False
                for hi in hi_segs:
                    for i in range(1, 13):
                        val = hi.get_value(i)
                        if val.upper().startswith('DR:') or val.upper().startswith('DR '):
                            has_drg = True
                            break
                    if has_drg:
                        break

                if not has_drg:
                    errors.append(ValidationError(
                        code='837I-DRG-MISSING',
                        severity='warning',
                        segment='HI',
                        element=None,
                        loop=loop.loop_id,
                        position=clm_seg.position,
                        message='Inpatient claim (CLM05-1=21) is missing a DRG code. '
                                'Add HI*DR:<drg_code>~ to the 2300 loop',
                    ))

        for child in loop.children:
            check_loop(child)

    for loop in loops:
        check_loop(loop)
    return errors


def luhn_check_rendering(loop: Loop) -> list[ValidationError]:
    """
    Validate rendering provider NPI (2310B NM109) using Luhn algorithm.
    """
    from validedi.handlers.npi import luhn_check
    errors: list[ValidationError] = []

    def check_loop(lp: Loop) -> None:
        if lp.loop_id == '2310B':
            for seg in lp.segments:
                if seg.segment_id == 'NM1':
                    npi = seg.get_value(9).strip()
                    if npi and len(npi) == 10 and npi.isdigit():
                        try:
                            if not luhn_check(npi):
                                errors.append(ValidationError(
                                    code='NPI_LUHN_2310B',
                                    severity='error',
                                    segment='NM1',
                                    element='NM109',
                                    loop='2310B',
                                    position=seg.position,
                                    message=f'Rendering provider NPI {npi} failed Luhn algorithm check',
                                ))
                        except ValueError:
                            pass
        for child in lp.children:
            check_loop(child)

    check_loop(loop)
    return errors


def diagnosis_decimal_check(loops: list[Loop]) -> list[ValidationError]:
    """
    Check for decimal points in ICD diagnosis codes within HI segments.
    X12 837 explicitly prohibits decimal points in diagnosis codes.
    """
    errors: list[ValidationError] = []

    def check_loop(loop: Loop) -> None:
        for seg in loop.segments:
            if seg.segment_id == 'HI':
                for i in range(1, 13):
                    val = seg.get_value(i).strip()
                    if not val:
                        continue
                    # Format is QUALIFIER:CODE — check the code part
                    code_part = val.split(':', 1)[1] if ':' in val else val
                    if '.' in code_part:
                        errors.append(ValidationError(
                            code='837-016',
                            severity='error',
                            segment='HI',
                            element=f'HI{i:02d}',
                            loop=loop.loop_id,
                            position=seg.position,
                            message=f'Diagnosis code {code_part!r} contains a decimal point. '
                                    f'X12 837 requires J18.9 to be submitted as J189',
                        ))
        for child in loop.children:
            check_loop(child)

    for loop in loops:
        check_loop(loop)
    return errors
