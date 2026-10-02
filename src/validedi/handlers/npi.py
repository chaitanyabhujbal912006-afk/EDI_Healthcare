"""
NPI (National Provider Identifier) validation using Luhn algorithm.
"""


def luhn_check(value: str) -> bool:
    """
    Validate NPI using Luhn algorithm with CMS prefix.
    
    The CMS NPI Luhn variant prefixes '80840' to the NPI before applying
    the standard Luhn check.
    
    Args:
        value: 10-digit NPI string
        
    Returns:
        True if NPI passes Luhn check, False otherwise
        
    Raises:
        ValueError: If value is not exactly 10 digits
    """
    if not value or len(value) != 10:
        raise ValueError(f'NPI must be exactly 10 digits, got {len(value) if value else 0}')
    
    if not value.isdigit():
        raise ValueError('NPI must contain only digits')
    
    # Prepend CMS prefix
    full_number = '80840' + value
    
    # Apply Luhn algorithm
    total = 0
    digits = [int(d) for d in full_number]
    
    # Process from right to left, doubling every second digit
    for i in range(len(digits) - 1, -1, -1):
        digit = digits[i]
        
        # Double every second digit from the right (excluding check digit)
        if (len(digits) - i) % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        
        total += digit
    
    # Check digit should make total divisible by 10
    return total % 10 == 0


def validate_npi_segments(loops: list) -> list:
    """Validate all NM1 segments with NM108=='XX' using Luhn algorithm."""
    from validedi.engine.models import ValidationError

    errors: list[ValidationError] = []

    def check_lp(lp):
        for seg in lp.segments:
            if seg.segment_id == "NM1" and len(seg.elements) >= 9:
                nm108 = seg.get_value(8).strip()
                nm109 = seg.get_value(9).strip()
                if nm108 == "XX" and nm109:
                    valid = False
                    if len(nm109) == 10 and nm109.isdigit():
                        try:
                            valid = luhn_check(nm109)
                        except ValueError:
                            valid = False
                    if not valid:
                        errors.append(
                            ValidationError(
                                code="NPI_INVALID",
                                severity="error",
                                segment="NM1",
                                element="NM109",
                                loop=lp.loop_id,
                                position=seg.position,
                                message="NM109 NPI is invalid. Expected 10-digit NPI with valid check digit.",
                            )
                        )
        for ch in lp.children:
            check_lp(ch)

    for l in loops:
        check_lp(l)
    return errors


def validate_billing_npi(loops: list) -> list:
    """Ensure billing provider NM1*85 has qualifier XX and a valid 10-digit NPI in NM109."""
    from validedi.engine.models import ValidationError

    errors: list[ValidationError] = []

    def check_lp(lp):
        for seg in lp.segments:
            if seg.segment_id == "NM1" and len(seg.elements) >= 1 and seg.get_value(1).strip() == "85":
                has_npi = (
                    len(seg.elements) >= 9
                    and seg.get_value(8).strip() == "XX"
                    and bool(seg.get_value(9).strip())
                )
                if not has_npi:
                    errors.append(
                        ValidationError(
                            code="BILLING_NPI_REQUIRED",
                            severity="error",
                            segment="NM1",
                            element="NM109",
                            loop="2010AA",
                            position=seg.position,
                            message=(
                                "Billing Provider (NM1*85) requires qualifier 'XX' in NM108 "
                                "and a valid 10-digit NPI in NM109."
                            ),
                        )
                    )
        for ch in lp.children:
            check_lp(ch)

    for l in loops:
        check_lp(l)
    return errors
