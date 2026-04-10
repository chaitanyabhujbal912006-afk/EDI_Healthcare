"""
Custom Exception Hierarchy

Exceptions:
- ValidEDIException (base)
  - ParseException
    - TokenizerException
    - EnvelopeException
    - LoopBuilderException
  - ValidationException
  - ExportException
  - ReconciliationException

All exceptions include:
- message: str
- location: Optional[str] (loop/segment location)
- code: Optional[str] (error code)

Used throughout the library for structured error handling.
"""
