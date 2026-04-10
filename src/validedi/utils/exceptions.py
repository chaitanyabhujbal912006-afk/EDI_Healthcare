"""
Exception hierarchy for ValidEDI library.
"""


class ValidEDIError(Exception):
    """Base exception for all ValidEDI errors."""
    pass


class EDIParseError(ValidEDIError):
    """
    Raised when the raw EDI string cannot be tokenized.
    Common causes: truncated ISA, unrecognized delimiters, malformed segments.
    """
    
    def __init__(self, message: str, raw_preview: str | None = None):
        super().__init__(message)
        self.raw_preview = raw_preview[:200] if raw_preview else None


class EDIValidationError(ValidEDIError):
    """
    Raised when validate() encounters a structural error so severe
    that a ValidationResult cannot even be assembled.
    Normal validation failures are returned as ValidationError objects
    inside ValidationResult — this exception is for catastrophic cases only.
    """
    pass


class UnsupportedTransactionError(ValidEDIError):
    """
    Raised by detector.py when the GS/ST codes identify a transaction type
    not present in registry.yaml. Allows callers to distinguish
    'bad EDI' from 'valid EDI we don't handle yet'.
    """
    
    def __init__(self, message: str, transaction_type_detected: str | None = None):
        super().__init__(message)
        self.transaction_type_detected = transaction_type_detected


class BadConfigError(ValidEDIError):
    """
    Raised by schema_validator.py or config_loader.py when a YAML
    configuration file fails its JSON Schema validation.
    """
    
    def __init__(
        self,
        message: str,
        config_file: str | None = None,
        schema_file: str | None = None,
        detail: str | None = None
    ):
        super().__init__(message)
        self.config_file = config_file
        self.schema_file = schema_file
        self.detail = detail
