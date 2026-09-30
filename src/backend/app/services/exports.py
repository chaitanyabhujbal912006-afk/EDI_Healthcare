from __future__ import annotations

import csv
import io
import json
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def json_bytes(data: Any) -> bytes:
    """Serialize *data* to indented UTF-8 JSON bytes."""
    return json.dumps(data, indent=2).encode("utf-8")


def csv_bytes(rows: list[dict[str, Any]], include_totals: bool = True) -> bytes:
    """Convert *rows* to CSV bytes with UTF-8 BOM for Excel compatibility.

    When *include_totals* is True and the data has numeric columns, a TOTAL
    summary row is appended at the bottom so analysts can spot aggregate values
    without building a pivot table.
    """
    if not rows:
        return b""

    fieldnames = list(rows[0].keys())
    out = io.StringIO()
    # UTF-8 BOM so Excel opens the file with correct encoding automatically
    out.write("\ufeff")
    writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)

    if include_totals and len(rows) > 1:
        totals: dict[str, Any] = {}
        has_numeric = False
        for field in fieldnames:
            col_vals = [r.get(field) for r in rows]
            numeric_vals = []
            for v in col_vals:
                try:
                    numeric_vals.append(float(v))  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    pass
            if len(numeric_vals) == len(rows):
                totals[field] = round(sum(numeric_vals), 2)
                has_numeric = True
            else:
                totals[field] = "TOTAL" if field == fieldnames[0] else ""
        if has_numeric:
            writer.writerow(totals)

    return out.getvalue().encode("utf-8")


def tsv_bytes(rows: list[dict[str, Any]]) -> bytes:
    """Convert *rows* to tab-separated values bytes (TSV).

    TSV is useful when field values may contain commas (e.g., provider names).
    """
    if not rows:
        return b""
    fieldnames = list(rows[0].keys())
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def error_report_pdf_bytes(issues: list[dict[str, Any]]) -> bytes:
    """Render a HIPAA EDI validation report as a PDF byte stream."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 40
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(30, y, "EDI Validation Report")

    y -= 24
    pdf.setFont("Helvetica", 10)

    for issue in issues:
        line = (
            f"[{issue.get('severity', '').upper()}] {issue.get('code', '')} | "
            f"{issue.get('segment_id', '')} | {issue.get('message', '')}"
        )
        pdf.drawString(30, y, line[:120])
        y -= 14
        if y < 40:
            pdf.showPage()
            y = height - 40
            pdf.setFont("Helvetica", 10)

    pdf.save()
    return buffer.getvalue()


