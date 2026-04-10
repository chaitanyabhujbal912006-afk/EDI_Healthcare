"""
ValidEDI - X12 EDI Parser and Validator

A library-first approach to parsing and validating healthcare EDI transactions.
Supports 837P, 837I, 835, and 834 transaction types.

Features:
- Parse and validate EDI files
- YAML-driven configuration
- LLM-powered explanations (bring your own LLM)
- Plain-English error messages
- Structured data extraction (claims, payments, enrollments)
- JSON export
"""

from validedi.engine.models import (
    ParsedEDI,
    ValidationResult,
    ValidationError,
    EnvelopeMeta,
    Loop,
    Segment,
    Element,
)
from validedi.utils.exceptions import (
    ValidEDIError,
    EDIParseError,
    EDIValidationError,
    UnsupportedTransactionError,
    BadConfigError,
)

# Import core functions
from validedi.engine.parser import parse
from validedi.engine.validator import validate

# Import extractors
from validedi.extractors import (
    extract_claims,
    extract_payments,
    extract_enrollments,
)

# Import exporters
from validedi.exporters import export_json

__version__ = "0.3.5"

__all__ = [
    # Core functions
    "parse",
    "validate",
    # Extractors
    "extract_claims",
    "extract_payments",
    "extract_enrollments",
    # Exporters
    "export_json",
    # Models
    "ParsedEDI",
    "ValidationResult",
    "ValidationError",
    "EnvelopeMeta",
    "Loop",
    "Segment",
    "Element",
    # Exceptions
    "ValidEDIError",
    "EDIParseError",
    "EDIValidationError",
    "UnsupportedTransactionError",
    "BadConfigError",
]

# LLM module is available as validedi.llm
# from validedi.llm import explain, ask_followup
