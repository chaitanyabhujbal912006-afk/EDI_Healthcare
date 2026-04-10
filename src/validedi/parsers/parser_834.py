"""
834 Benefit Enrollment and Maintenance Parser

Parses 834 enrollment/eligibility files.

Loop hierarchy:
- Loop 1000A/B: Sponsor/Payer
- Loop 2000: Member Level (one per enrollee)
- Loop 2100A-H: Member Names (subscriber, spouse, dependents)
- Loop 2300: Health Coverage (HD segment)
- Loop 2310: Provider Information
- Loop 2320: Coordination of Benefits (COB)
- Loop 2700: Member Reporting Categories

Key segments:
- INS: Member maintenance type (001=change, 021=add, 024=term, 025=reinstate)
- REF: Member IDs (0F=subscriber, 1L=group)
- NM1: Member name
- HD: Health coverage details
- DTP: Dates (348=coverage start, 349=coverage end)

Special handling:
- Maintenance type code interpretation
- Duplicate member detection
- Date consistency validation (effective dates, DOB)
- Family/dependent relationship tracking

Input: Tokenized segments
Output: Hierarchical loop tree with member enrollment data
"""
