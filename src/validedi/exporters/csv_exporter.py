"""
CSV export functionality for parsed EDI validation results.

Provides two main functions:
- export_errors_csv: Export validation errors as CSV rows
- export_claims_csv: Export extracted 837P/837I claim lines as CSV rows

Both functions accept an optional ``filepath`` argument; when omitted they
return the CSV content as a string so callers can embed it in an API
response without touching the filesystem.
"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from validedi.engine.models import ParsedEDI, ValidationResult

# ── Column definitions ──────────────────────────────────────────────────────

_ERROR_COLUMNS = [
    "severity",
    "code",
    "segment",
    "element",
    "loop",
    "position",
    "message",
]

_CLAIM_COLUMNS = [
    "claim_id",
    "patient_name",
    "provider_npi",
    "service_date",
    "total_charge",
    "place_of_service",
    "diagnosis_codes",
    "procedure_code",
    "procedure_charge",
]


# ── Public helpers ──────────────────────────────────────────────────────────


def export_errors_csv(
    validation_result: "ValidationResult",
    filepath: str | None = None,
) -> str:
    """
    Export validation errors from a ``ValidationResult`` to CSV format.

    Args:
        validation_result: A ``ValidationResult`` object produced by
            :func:`validedi.validate`.
        filepath: Optional path to write the CSV file.  When *None* the
            CSV content is returned as a ``str`` instead.

    Returns:
        CSV content as a string (when ``filepath`` is *None*), otherwise
        an empty string after writing the file.

    Example::

        result = validate("claim.edi")
        csv_str = export_errors_csv(result)
        # or write to file:
        export_errors_csv(result, "errors.csv")
    """
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_ERROR_COLUMNS, lineterminator="\n")
    writer.writeheader()

    for err in validation_result.errors:
        writer.writerow(
            {
                "severity": err.severity,
                "code": err.code,
                "segment": err.segment,
                "element": err.element or "",
                "loop": err.loop or "",
                "position": err.position,
                "message": err.message,
            }
        )

    content = buf.getvalue()

    if filepath:
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        return ""

    return content


def export_claims_csv(
    parsed_edi: "ParsedEDI",
    filepath: str | None = None,
) -> str:
    """
    Export extracted claim lines from an 837P or 837I ``ParsedEDI`` to CSV.

    Each row represents a single service line within a claim.  When the
    transaction type is not ``837p`` or ``837i`` an empty CSV with only the
    header row is returned.

    Args:
        parsed_edi: A ``ParsedEDI`` object produced by :func:`validedi.parse`.
        filepath: Optional path to write the CSV file.  When *None* the
            CSV content is returned as a ``str`` instead.

    Returns:
        CSV content as a string (when ``filepath`` is *None*), otherwise
        an empty string after writing the file.

    Example::

        parsed = parse("claim.edi")
        csv_str = export_claims_csv(parsed)
    """
    from validedi.extractors import extract_claims  # local import avoids circulars

    rows: list[dict[str, Any]] = []

    tx_type = parsed_edi.envelope.transaction_type
    if tx_type in ("837p", "837i"):
        try:
            claims = extract_claims(parsed_edi)
            for claim in claims:
                base: dict[str, Any] = {
                    "claim_id": claim.get("claim_id", ""),
                    "patient_name": claim.get("patient_name", ""),
                    "provider_npi": claim.get("provider_npi", ""),
                    "service_date": claim.get("service_date", ""),
                    "total_charge": claim.get("total_charge", ""),
                    "place_of_service": claim.get("place_of_service", ""),
                    "diagnosis_codes": "|".join(claim.get("diagnosis_codes", [])),
                }
                service_lines = claim.get("service_lines", [])
                if service_lines:
                    for line in service_lines:
                        row = {**base}
                        row["procedure_code"] = line.get("procedure_code", "")
                        row["procedure_charge"] = line.get("charge", "")
                        rows.append(row)
                else:
                    base["procedure_code"] = ""
                    base["procedure_charge"] = ""
                    rows.append(base)
        except Exception:
            pass  # Extraction errors produce an empty CSV rather than raising

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CLAIM_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    content = buf.getvalue()

    if filepath:
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        return ""

    return content
