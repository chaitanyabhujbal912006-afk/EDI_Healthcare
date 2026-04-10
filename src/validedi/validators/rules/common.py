"""
Common validation rules shared across all transaction types

Functions:
- validate_npi(npi: str) -> bool
  Luhn algorithm check for 10-digit NPI
  
- validate_date(date_str: str, format: str = "CCYYMMDD") -> bool
  Date format and plausibility check
  
- validate_zip(zip_code: str) -> bool
  5-digit or 9-digit ZIP code format
  
- validate_amount(amount: str) -> bool
  Monetary amount format (decimal, max 2 places)
  
- validate_qualifier(qualifier: str, allowed: List[str]) -> bool
  Check if qualifier is in allowed list
  
- check_required_segment(loop: Loop, segment_id: str) -> Optional[ValidationError]
  Verify required segment exists in loop

All functions return ValidationError objects or None.
"""
