"""
834 Enrollment-specific validation rules

Rules:
- INS maintenance type code validation (001, 021, 024, 025, 030)
- INS relationship code validation (18=self, 01=spouse, 19=child, etc.)
- Duplicate member detection (same subscriber ID + SSN)
- Date consistency:
  - Coverage effective date <= coverage end date
  - DOB < coverage effective date
  - Termination date >= coverage start date
- HD (health coverage) segment validation
- COB (coordination of benefits) validation
- Dependent age vs relationship code consistency
- Required segments per maintenance type:
  - 021 (add): REF, NM1, HD, DTP*348 required
  - 024 (term): DTP*349 required

Special handling:
- Family/dependent relationship tracking
- Maintenance type-specific required fields
"""
