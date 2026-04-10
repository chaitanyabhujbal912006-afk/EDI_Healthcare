"""
Date Utilities

Functions:
- parse_edi_date(date_str: str, format: str = "CCYYMMDD") -> date
  Parses EDI date string to Python date object
  Supports: CCYYMMDD, CCYYMM, CCYY
  
- validate_date_format(date_str: str, format: str = "CCYYMMDD") -> bool
  Checks if date string matches expected format
  
- validate_date_plausibility(date: date) -> bool
  Checks if date is reasonable (not in far future, not before 1900)
  
- compare_dates(date1: date, date2: date, operator: str) -> bool
  Compares two dates with operator: <, <=, >, >=, ==
  
- calculate_age(dob: date, reference_date: date) -> int
  Calculates age in years

Used by validators for date consistency checks.
"""
