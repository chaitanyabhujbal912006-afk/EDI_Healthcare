"""
835↔837 Reconciliation Engine

Matches 835 remittance claims against 837 submitted claims.

Matching logic:
- Primary: ICN (Internal Control Number) from REF*D9 in 837 vs CLP01 in 835
- Fallback: DCN (Document Control Number) from REF*F8
- Fuzzy: Patient name + service date + billed amount

Output model:
- matched_claims: List[MatchedClaim]
  - claim_837: Claim837
  - claim_835: Claim835
  - variance: Decimal (billed vs paid difference)
  - adjustment_summary: str
- unmatched_837: List[Claim837] (submitted but not paid)
- unmatched_835: List[Claim835] (paid but no submission found)

Functions:
- reconcile(parse_result_837: ParseResult, parse_result_835: ParseResult) -> ReconciliationResult
- calculate_variance(claim_837: Claim837, claim_835: Claim835) -> Decimal
- export_to_csv() -> str

Used by backend reconcile endpoint and frontend ReconcileView.tsx
"""
