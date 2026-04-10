"""
837P Professional Claims Parser

Parses 837 Professional (physician/outpatient) claims.

Loop hierarchy:
- Loop 1000A/B: Submitter/Receiver
- Loop 2000A: Billing Provider Hierarchical Level
- Loop 2010AA/AB: Billing/Pay-To Provider Name
- Loop 2000B: Subscriber Hierarchical Level
- Loop 2010BA/BB: Subscriber/Payer Name
- Loop 2000C: Patient Hierarchical Level (if different from subscriber)
- Loop 2300: Claim Information
- Loop 2310A-E: Referring/Rendering/Service Facility Provider
- Loop 2400: Service Line
- Loop 2420A-E: Service Line Provider

Key segments: NM1, N3, N4, PRV, REF, PER, CLM, HI, SV1, DTP

Input: Tokenized segments
Output: Hierarchical loop tree with 837P-specific structure
"""
