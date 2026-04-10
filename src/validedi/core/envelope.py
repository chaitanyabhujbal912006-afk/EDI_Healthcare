"""
Envelope Parser - ISA/GS/ST/SE/GE/IEA metadata extractor

Responsibilities:
- Parse interchange envelope (ISA/IEA)
- Parse functional group envelope (GS/GE)
- Parse transaction set envelope (ST/SE)
- Extract metadata: sender/receiver IDs, dates, control numbers, version
- Validate envelope structure and control number consistency
- Return structured Envelope model

Input: List of segments
Output: Envelope Pydantic model with metadata
"""
