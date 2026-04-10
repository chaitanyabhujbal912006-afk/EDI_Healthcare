"""
835 Remittance Advice Parser

Parses 835 Health Care Claim Payment/Advice (remittance/ERA).

Loop hierarchy:
- Loop 1000A/B: Payer/Payee Identification
- Loop 2000: Header (claim-level or payment-level)
- Loop 2100: Claim Payment Information (CLP)
- Loop 2110: Service Payment Information (SVC)

Key segments:
- CLP: Claim payment info (claim ID, status, billed, paid, patient responsibility)
- CAS: Claim/service adjustment (reason codes, amounts)
- SVC: Service line payment
- PLB: Provider-level adjustments

Special handling:
- CAS adjustment reason code validation (CARC/RARC)
- Group code validation (CO, PR, OA, PI)
- Reconciliation with 837 claims

Input: Tokenized segments
Output: Hierarchical loop tree with payment details
"""
