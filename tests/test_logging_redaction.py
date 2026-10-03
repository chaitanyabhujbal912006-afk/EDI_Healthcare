"""
Unit tests for structured JSON logging and PHI redaction filter.
Validates:
- PHIRedactionFilter redacts SSN (hyphenated and 9-digit)
- PHIRedactionFilter redacts 8-digit dates (YYYYMMDD, YYYY-MM-DD, MM/DD/YYYY)
- PHIRedactionFilter redacts 8+ char alphanumeric IDs (MEM123456, ABC12345, etc.)
- Normal English words (application, validation, processing) are preserved
- JSONFormatter produces valid JSON with fields: ts, level, logger, request_id, message
- Request ID context propagation works as expected
"""
from __future__ import annotations

import json
import logging

from app.logging_config import (
    JSONFormatter,
    PHIRedactionFilter,
    redact_phi,
    request_id_ctx,
)


def test_redact_phi_ssn():
    # Hyphenated SSN
    msg1 = "Patient SSN is 123-45-6789 in record"
    assert redact_phi(msg1) == "Patient SSN is [REDACTED] in record"

    # Standalone 9-digit number
    msg2 = "Tax ID: 987654321 for provider"
    assert redact_phi(msg2) == "Tax ID: [REDACTED] for provider"


def test_redact_phi_dates():
    # 8-digit date YYYYMMDD
    msg1 = "DOB: 19850615 in demographic segment"
    assert redact_phi(msg1) == "DOB: [REDACTED] in demographic segment"

    # Hyphenated date
    msg2 = "Service date: 2024-05-12 confirmed"
    assert redact_phi(msg2) == "Service date: [REDACTED] confirmed"

    # Slash date
    msg3 = "Admitted on 01/15/2023 at noon"
    assert redact_phi(msg3) == "Admitted on [REDACTED] at noon"


def test_redact_phi_alphanumeric_ids():
    # 8+ char alphanumeric IDs
    msg1 = "Member ID MEM12345678 verified"
    assert redact_phi(msg1) == "Member ID [REDACTED] verified"

    msg2 = "Claim tracking code ABC12345 processed"
    assert redact_phi(msg2) == "Claim tracking code [REDACTED] processed"

    msg3 = "Subscriber identifier A1B2C3D4 found"
    assert redact_phi(msg3) == "Subscriber identifier [REDACTED] found"

    msg4 = "10-digit NPI or ID 1234567890 mapped"
    assert redact_phi(msg4) == "10-digit NPI or ID [REDACTED] mapped"


def test_preserves_standard_english_words():
    # Ordinary technical words >= 8 characters must NOT be redacted
    msg = "Starting application validation middleware and processing configuration"
    redacted = redact_phi(msg)
    assert "application" in redacted
    assert "validation" in redacted
    assert "middleware" in redacted
    assert "processing" in redacted
    assert "configuration" in redacted
    assert "[REDACTED]" not in redacted


def test_phi_redaction_filter_on_log_record():
    redaction_filter = PHIRedactionFilter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Patient 123-45-6789 with ID MEM99887766 born 19751225",
        args=(),
        exc_info=None,
    )
    result = redaction_filter.filter(record)
    assert result is True
    assert "123-45-6789" not in record.msg
    assert "MEM99887766" not in record.msg
    assert "19751225" not in record.msg
    assert record.msg == "Patient [REDACTED] with ID [REDACTED] born [REDACTED]"


def test_phi_redaction_filter_with_args():
    redaction_filter = PHIRedactionFilter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=12,
        msg="Processing member %s with SSN %s",
        args=("SUB12345678", "000-11-2222"),
        exc_info=None,
    )
    redaction_filter.filter(record)
    assert record.args == ("[REDACTED]", "[REDACTED]")
    formatted = record.getMessage()
    assert "SUB12345678" not in formatted
    assert "000-11-2222" not in formatted
    assert formatted == "Processing member [REDACTED] with SSN [REDACTED]"


def test_json_formatter_fields_and_redaction():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="edipro.gateway",
        level=logging.WARNING,
        pathname="gateway.py",
        lineno=42,
        msg="Failed claim for patient ID PAT98765432, DOB 19900101",
        args=(),
        exc_info=None,
    )

    # Set request_id via context var
    token = request_id_ctx.set("req-abc-12345")
    try:
        output = formatter.format(record)
    finally:
        request_id_ctx.reset(token)

    data = json.loads(output)
    # Required fields: ts, level, logger, request_id, message
    assert "ts" in data
    assert data["level"] == "WARNING"
    assert data["logger"] == "edipro.gateway"
    assert data["request_id"] == "req-abc-12345"
    assert "message" in data

    # Verify message is redacted in JSON output
    assert "PAT98765432" not in data["message"]
    assert "19900101" not in data["message"]
    assert "[REDACTED]" in data["message"]


def test_json_formatter_without_request_id():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="edipro.worker",
        level=logging.INFO,
        pathname="worker.py",
        lineno=20,
        msg="Worker background job started",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["request_id"] is None
    assert data["level"] == "INFO"
    assert data["message"] == "Worker background job started"
