"""Deprecated: Use app.adapters instead."""
from __future__ import annotations

from app.adapters import parse_edi_content as parse_x12
from app.adapters import to_segment_text

__all__ = ["parse_x12", "to_segment_text"]
