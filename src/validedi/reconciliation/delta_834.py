"""
834 Delta Report Generator

Compares two consecutive 834 files (e.g., month-over-month) and identifies changes.

Change types:
- New members: Present in file2, not in file1
- Terminated members: Present in file1, not in file2
- Modified members: Present in both, but attributes changed
  - Coverage type change
  - Dependent added/removed
  - Address change
  - COB change

Output model:
- new_members: List[Member]
- terminated_members: List[Member]
- modified_members: List[MemberDelta]
  - member_id: str
  - changes: Dict[str, Tuple[old_value, new_value]]

Functions:
- generate_delta(parse_result_old: ParseResult, parse_result_new: ParseResult) -> DeltaReport
- export_to_csv() -> str

Used by backend reconcile endpoint and frontend DeltaReport.tsx
"""
