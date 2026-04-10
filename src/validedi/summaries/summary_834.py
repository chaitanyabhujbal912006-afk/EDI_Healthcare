"""
834 Enrollment Summary Generator

Extracts member enrollment information from Loop 2000 and formats as tabular data.

Output model:
- member_id: str (from REF*0F)
- subscriber_id: str (from REF*0F in subscriber loop)
- group_number: str (from REF*1L)
- maintenance_type: str (from INS03: 001, 021, 024, 025, 030)
- maintenance_type_label: str (Change, Add, Term, Reinstate, Audit)
- relationship_code: str (from INS02: 18=self, 01=spouse, 19=child)
- first_name: str (from NM104)
- last_name: str (from NM103)
- dob: date (from DMG02)
- coverage_start: date (from DTP*348)
- coverage_end: date (from DTP*349)
- coverage_type: str (from HD segment)
- cob_indicator: bool (from Loop 2320)

Functions:
- generate_summary(parse_result: ParseResult) -> EnrollmentSummary
- export_to_table() -> List[Dict]
- group_by_family() -> Dict[str, List[Member]]
- color_code_maintenance_type(type: str) -> str (for UI)

Used by backend summary endpoint and frontend EnrollmentSummary.tsx
"""
