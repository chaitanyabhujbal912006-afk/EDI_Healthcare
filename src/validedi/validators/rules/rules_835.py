"""
835 Remittance-specific validation rules

Rules:
- CLP status code validation (1=processed, 2=finalized, etc.)
- CAS adjustment reason code validation against CARC list
- CAS group code validation (CO, PR, OA, PI)
- RARC (Remittance Advice Remark Code) validation
- CLP amount reconciliation: billed - adjustments = paid + patient resp
- SVC line-level reconciliation
- PLB provider adjustment validation
- Check/EFT trace number format

Special handling:
- Cross-reference CARC/RARC code sets
- Validate adjustment amounts sum correctly
"""
