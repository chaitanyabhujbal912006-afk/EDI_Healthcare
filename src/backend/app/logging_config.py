"""
Structured JSON logging and PHI redaction filter for EdiPro Healthcare EDI Gateway.
Provides:
- PHIRedactionFilter: Redacts SSNs, 8+ char alphanumeric IDs, and 8-digit dates.
- JSONFormatter: Emits JSON log records with ts, level, logger, request_id, and message.
- Context-aware request_id tracking via ContextVar.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# Context variable for tracking request ID across async tasks
request_id_ctx: ContextVar[str | None] = ContextVar("request_id_ctx", default=None)

# Redaction patterns:
# 1. SSN: 3 digits - 2 digits - 4 digits OR standalone 9-digit numbers
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b")

# 2. 8-digit dates:
# YYYYMMDD, MMDDYYYY, YYYY-MM-DD, MM/DD/YYYY, etc.
DATE_PATTERN = re.compile(
    r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b|\b\d{1,2}[-/.]\d{1,2}\b[-/.]\d{4}\b|\b\d{8}\b"
)

# 3. 8+ char alphanumeric IDs:
# Alphanumeric tokens of 8+ characters containing letters and numbers (or 8+ consecutive digits)
ALPHANUMERIC_ID_PATTERN = re.compile(
    r"\b(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{8,}\b|\b\d{8,}\b"
)

REDACTED_TEXT = "[REDACTED]"


def redact_phi(text: str, replacement: str = REDACTED_TEXT) -> str:
    """Redact any SSN, 8-digit date, or 8+ char alphanumeric ID from text."""
    if not isinstance(text, str) or not text:
        return text
    text = SSN_PATTERN.sub(replacement, text)
    text = DATE_PATTERN.sub(replacement, text)
    text = ALPHANUMERIC_ID_PATTERN.sub(replacement, text)
    return text


class PHIRedactionFilter(logging.Filter):
    """
    Logging filter that redacts SSNs, 8+ character alphanumeric IDs,
    and 8-digit dates from log messages and arguments.
    """

    def __init__(self, replacement: str = REDACTED_TEXT, name: str = "") -> None:
        super().__init__(name=name)
        self.replacement = replacement

    def redact(self, text: str) -> str:
        return redact_phi(text, self.replacement)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)

        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    self.redact(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: self.redact(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }

        # If record already had .message computed
        if hasattr(record, "message") and isinstance(record.message, str):
            record.message = self.redact(record.message)

        return True


class JSONFormatter(logging.Formatter):
    """
    Structured JSON log formatter outputting:
    - ts: ISO-8601 UTC timestamp
    - level: log level name
    - logger: logger name
    - request_id: request_id from record or contextvar
    - message: formatted, redacted message
    """

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: Any = "%",
        validate: bool = True,
    ) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt, style=style, validate=validate)

    def format(self, record: logging.LogRecord) -> str:
        # Determine message
        try:
            msg = record.getMessage()
        except (TypeError, ValueError, AttributeError):
            msg = str(record.msg)

        # Redact as safety net
        msg = redact_phi(msg)

        # Determine request_id
        req_id = getattr(record, "request_id", None)
        if not req_id:
            req_id = request_id_ctx.get(None)

        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

        entry: dict[str, Any] = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "request_id": req_id,
            "message": msg,
        }

        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry)


def setup_logging(level: int = logging.INFO) -> logging.Handler:
    """Configure root logger with JSONFormatter and PHIRedactionFilter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(PHIRedactionFilter())

    root_logger.addHandler(handler)
    return handler
