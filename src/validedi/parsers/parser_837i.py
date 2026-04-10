"""
837I Institutional Claims Parser

Parses 837 Institutional (hospital/facility) claims.

Loop hierarchy differences from 837P:
- Loop 2300: Uses CLM segment with institutional-specific elements
- Loop 2400: Uses SV2 (institutional service line) instead of SV1
- Additional loops: 2310E (Attending Provider), 2310F (Operating Provider)
- Different qualifier codes and element positions

Key segments: NM1, N3, N4, CLM, HI, SV2, DTP, REF

Input: Tokenized segments
Output: Hierarchical loop tree with 837I-specific structure
"""
