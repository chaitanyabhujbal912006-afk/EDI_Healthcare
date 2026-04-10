"""
EDI Exporter

Serializes corrected loop tree back to X12 delimited format.

Process:
1. Traverse loop tree in correct order
2. Serialize each segment with proper delimiters
3. Apply fixes if provided
4. Recalculate control numbers (SE01, GE01, IEA01)
5. Output valid X12 string

Functions:
- export_edi(parse_result: ParseResult, fixes: Optional[List[Fix]] = None) -> str
- export_edi_file(parse_result: ParseResult, path: str, fixes: Optional[List[Fix]] = None) -> None

Used by backend export endpoint and fix workflow.
"""
