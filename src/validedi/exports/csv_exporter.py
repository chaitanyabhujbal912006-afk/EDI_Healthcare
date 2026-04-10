"""
CSV Exporter

Exports 834 member roster to CSV format.

Columns:
- Member ID
- Subscriber ID
- Group Number
- Maintenance Type
- Relationship
- First Name
- Last Name
- DOB
- Coverage Start
- Coverage End
- Coverage Type

Functions:
- export_csv(parse_result: ParseResult) -> str
- export_csv_file(parse_result: ParseResult, path: str) -> None

Only applicable to 834 transactions.
Used by backend export endpoint.
"""
