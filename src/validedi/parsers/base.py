"""
BaseParser - Abstract base class for all transaction parsers

Defines the parsing contract that all transaction-specific parsers must implement:
- parse(segments: List[str]) -> ParseResult
- get_loop_definitions() -> Dict[str, LoopDefinition]
- identify_loop_start(segment: str) -> Optional[str]

Provides shared utility methods:
- split_segment(segment: str) -> List[str]
- extract_element(segment: str, position: int) -> str
- validate_segment_count(segment: str, expected: int) -> bool

All transaction parsers (837P, 837I, 835, 834) inherit from this.
"""
