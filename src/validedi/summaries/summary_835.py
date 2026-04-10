"""
835 Remittance Summary Generator

Extracts claim payment information from CLP loops and formats as tabular data.

Output model:
- claim_id: str (from CLP02)
- status_code: str (from CLP03)
- billed_amount: Decimal (from CLP04)
- paid_amount: Decimal (from CLP05)
- patient_responsibility: Decimal (from CLP06)
- adjustments: List[Adjustment] (from CAS segments)
  - group_code: str (CO, PR, OA, PI)
  - reason_code: str (CARC)
  - amount: Decimal
- check_eft_trace: str (from TRN segment)

Functions:
- generate_summary(parse_result: ParseResult) -> RemittanceSummary
- export_to_table() -> List[Dict]

Used by backend summary endpoint and frontend RemittanceSummary.tsx
"""
