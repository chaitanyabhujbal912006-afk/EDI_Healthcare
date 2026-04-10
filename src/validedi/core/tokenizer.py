"""
Tokenizer - Raw EDI file to segment list converter

Responsibilities:
- Detect delimiters from ISA segment (ISA16 for segment, ISA16-1 for element, ISA16-2 for sub-element)
- Split raw EDI string into individual segments
- Handle edge cases: escaped delimiters, whitespace, encoding issues
- Return list of raw segment strings for further processing

Input: Raw EDI file content (string)
Output: List of segment strings + delimiter metadata
"""
