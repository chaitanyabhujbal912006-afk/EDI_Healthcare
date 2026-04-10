"""
Core Pydantic Models

Defines data structures used throughout the library:
- Segment: Individual EDI segment (e.g., NM1*IL*1*SMITH*WILLIAM)
- Element: Single data element within a segment
- Loop: Hierarchical container for segments and child loops
- Envelope: ISA/GS/ST metadata
- ValidationError: Error/warning with location, code, message, severity
- ParseResult: Complete parsed file structure

All models use Pydantic v2 for type safety, validation, and serialization.
"""
