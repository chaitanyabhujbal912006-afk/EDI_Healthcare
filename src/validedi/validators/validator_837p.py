"""
837P Professional Claims Validator

Orchestrates validation for 837P transactions.
Applies rules from: rules_837.py (shared) + rules_837p.py (professional-specific) + common.py

Validation flow:
1. Envelope validation
2. Loop structure validation
3. Segment-level validation (required segments, element formats)
4. Cross-segment consistency checks
5. Business rule validation

Returns: List[ValidationError] with location, code, message, severity
"""
