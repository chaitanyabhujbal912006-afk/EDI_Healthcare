"""
835 Remittance Validator

Orchestrates validation for 835 transactions.
Applies rules from: rules_835.py + common.py

Special focus:
- CAS adjustment reason code validation
- CLP amount reconciliation
- Group code validation

Returns: List[ValidationError]
"""
