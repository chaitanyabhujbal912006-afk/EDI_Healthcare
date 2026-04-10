"""
JSON Exporter

Serializes parsed loop tree structure to JSON.

Output format:
{
  "envelope": {...},
  "transaction_type": "837P",
  "loops": [
    {
      "loop_id": "2000A",
      "segments": [...],
      "children": [...]
    }
  ]
}

Functions:
- export_json(parse_result: ParseResult) -> Dict
- export_json_string(parse_result: ParseResult) -> str

Used by backend export endpoint and frontend export menu.
"""
