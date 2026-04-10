"""
834 Enrollment Validator

Orchestrates validation for 834 transactions.
Applies rules from: rules_834.py + common.py

Special focus:
- INS maintenance type code validation
- Duplicate member detection
- Date consistency checks
- Maintenance type-specific required fields

Returns: List[ValidationError]
"""
