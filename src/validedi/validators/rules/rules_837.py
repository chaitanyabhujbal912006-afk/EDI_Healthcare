"""
Shared 837 validation rules (both Professional and Institutional)

Rules:
- CLM segment structure validation
- HI (diagnosis) segment format
- Patient vs subscriber relationship consistency
- Claim date vs service date consistency
- Total claim charge vs sum of service line charges
- NM1 qualifier validation (IL, PR, DN, 82, etc.)
- REF qualifier validation
- DTP date type qualifier validation

Used by both validator_837p.py and validator_837i.py
"""
