"""
Format Validation Utilities

Functions:
- validate_zip(zip_code: str) -> bool
  Validates 5-digit or 9-digit ZIP code format
  
- validate_amount(amount: str) -> bool
  Validates monetary amount format (decimal, max 2 places)
  
- format_amount(amount: str) -> Decimal
  Converts amount string to Decimal
  
- validate_phone(phone: str) -> bool
  Validates phone number format
  
- validate_qualifier(qualifier: str, allowed: List[str]) -> bool
  Checks if qualifier is in allowed list
  
- normalize_string(s: str) -> str
  Removes extra whitespace, converts to uppercase

Used by validators for element format checks.
"""
