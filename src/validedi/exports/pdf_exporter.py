"""
PDF Exporter

Generates validation report PDF using ReportLab.

Report sections:
1. File metadata (sender, receiver, date, transaction type)
2. Summary statistics (total segments, loops, errors, warnings)
3. Error report table (location, code, message, severity)
4. Business summary (835 payment table or 834 member table)

Functions:
- export_pdf(parse_result: ParseResult, errors: List[ValidationError]) -> bytes
- export_pdf_file(parse_result: ParseResult, errors: List[ValidationError], path: str) -> None

Used by backend export endpoint.
"""
