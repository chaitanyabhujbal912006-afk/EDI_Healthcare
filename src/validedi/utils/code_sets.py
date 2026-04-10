"""
Code Set Lookup Tables

Constants:
- CARC_CODES: Dict[str, str]
  Claim Adjustment Reason Codes (e.g., "1": "Deductible Amount")
  
- RARC_CODES: Dict[str, str]
  Remittance Advice Remark Codes
  
- GROUP_CODES: List[str]
  Valid group codes: CO, PR, OA, PI
  
- INS_MAINTENANCE_TYPES: Dict[str, str]
  834 maintenance type codes (001, 021, 024, 025, 030)
  
- INS_RELATIONSHIP_CODES: Dict[str, str]
  Relationship codes (18=self, 01=spouse, 19=child, etc.)
  
- PLACE_OF_SERVICE_CODES: Dict[str, str]
  837P place of service codes (11=office, 21=inpatient, etc.)
  
- QUALIFIER_CODES: Dict[str, List[str]]
  Allowed qualifier codes per segment/element

Functions:
- lookup_carc(code: str) -> Optional[str]
- lookup_rarc(code: str) -> Optional[str]
- is_valid_group_code(code: str) -> bool

Used by validators and summaries for code validation and display.
"""
