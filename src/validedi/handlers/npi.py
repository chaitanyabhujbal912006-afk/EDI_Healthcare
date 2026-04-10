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
        raise ValueError(f'NPI must contain only digits')
    
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
