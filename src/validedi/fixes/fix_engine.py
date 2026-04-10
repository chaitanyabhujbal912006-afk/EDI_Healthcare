"""
Fix Engine - Deterministic error correction suggestions

Maps known error patterns to suggested corrections.

Supported fix types:
- NPI format errors: add leading zeros, remove invalid characters
- Date format errors: convert MM/DD/YYYY to CCYYMMDD
- ZIP code format: pad to 5 digits
- Missing required segments: suggest template segment
- Invalid qualifier codes: suggest correct qualifier from allowed list
- Amount format: round to 2 decimal places, remove currency symbols

Functions:
- suggest_fix(error: ValidationError, context: Loop) -> Optional[Fix]
- apply_fix(fix: Fix, parse_result: ParseResult) -> ParseResult
- get_fixable_errors(errors: List[ValidationError]) -> List[ValidationError]

Returns Fix objects with:
- error_code: str
- suggested_value: str
- confidence: float (0.0-1.0)
- explanation: str
"""
