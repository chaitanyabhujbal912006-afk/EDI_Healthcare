"""
834 Eligibility Cross-Check

Validates 837 claims against 834 enrollment roster.

Checks:
- Is subscriber ID in 837 present in 834 roster?
- Is claim service date within coverage effective dates?
- Is member terminated before claim date?
- Is member not yet effective at claim date?
- Does coverage type match claim type (medical vs dental)?

Output model:
- valid_claims: List[Claim837]
- invalid_claims: List[EligibilityError]
  - claim_id: str
  - subscriber_id: str
  - error_type: str (not_found, terminated, not_effective, coverage_mismatch)
  - claim_date: date
  - coverage_start: date
  - coverage_end: date

Functions:
- check_eligibility(parse_result_837: ParseResult, parse_result_834: ParseResult) -> EligibilityCheckResult
- export_to_csv() -> str

Used by backend reconcile endpoint and frontend EligibilityCheck.tsx
"""
