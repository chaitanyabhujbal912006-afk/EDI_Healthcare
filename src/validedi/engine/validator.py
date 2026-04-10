"""
Main validate function - entry point for EDI validation.
"""

from pathlib import Path
from validedi.engine.models import ValidationResult, ParsedEDI
from validedi.engine.parser import parse
from validedi.engine.config_loader import get_config
from validedi.engine.rule_executor import RuleExecutor


def validate(source: str | Path | ParsedEDI) -> ValidationResult:
    """
    Parse and validate EDI file or string, or validate already-parsed EDI.
    
    Args:
        source: Either:
                - A file path (str/Path) - reads and parses the file
                - Raw EDI string - parses the string
                - ParsedEDI object - validates already-parsed data
        
    Returns:
        ValidationResult with parsed data and validation errors
        
    Raises:
        EDIParseError: If EDI cannot be parsed
        UnsupportedTransactionError: If transaction type not supported
        FileNotFoundError: If file path doesn't exist
    
    Examples:
        # Validate from file
        result = validate('claim.edi')
        result = validate('/path/to/file.edi')
        result = validate(Path('claim.edi'))
        
        # Validate from string
        result = validate('ISA*00*...')
        
        # Validate already-parsed EDI
        parsed = parse('claim.edi')
        result = validate(parsed)
    """
    # Check if already parsed
    if isinstance(source, ParsedEDI):
        parsed = source
    else:
        # Parse the EDI (handles both file and string)
        parsed = parse(source)
    
    # Load configuration
    config = get_config(parsed.envelope.transaction_type)
    
    # Execute validation rules
    executor = RuleExecutor(config)
    errors = executor.execute_all(parsed.loops, parsed)
    
    return ValidationResult(
        parsed=parsed,
        errors=errors
    )
