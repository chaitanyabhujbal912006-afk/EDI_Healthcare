from __future__ import annotations

import csv
import io
import json
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def json_bytes(data: Any) -> bytes:
    return json.dumps(data, indent=2).encode("utf-8")


def csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def error_report_pdf_bytes(issues: list[dict[str, Any]]) -> bytes:
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

