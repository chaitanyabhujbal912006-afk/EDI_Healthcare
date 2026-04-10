"""
Pydantic models for ValidEDI data structures.
"""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Element(BaseModel):
    """Represents a single element within a segment."""
    
    raw: str
    components: list[str] = Field(default_factory=list)
    
    model_config = ConfigDict(populate_by_name=True)
    
    def get(self, n: int) -> str:
        """
        Get composite component by 1-based index (EDI convention).
        Returns empty string if index out of range.
        """
        return self.components[n - 1] if 0 < n <= len(self.components) else ''


class Segment(BaseModel):
    """Represents a single EDI segment."""
    
    segment_id: str
    elements: list[Element] = Field(default_factory=list)
    position: int
    
    model_config = ConfigDict(populate_by_name=True)
    
    def get(self, n: int) -> Element:
        """
        Get element by 1-based index (EDI convention).
        Returns empty Element if index out of range.
        """
        if 0 < n <= len(self.elements):
            return self.elements[n - 1]
        return Element(raw='', components=[])
    
    def get_value(self, n: int) -> str:
        """Get element value by 1-based index."""
        return self.get(n).raw


class Loop(BaseModel):
    """Represents a hierarchical loop structure."""
    
    loop_id: str
    segments: list[Segment] = Field(default_factory=list)
    children: list['Loop'] = Field(default_factory=list)
    
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)
    
    def find_segment(self, seg_id: str) -> Segment | None:
        """Find first segment with given ID in direct segments."""
        for segment in self.segments:
            if segment.segment_id == seg_id:
                return segment
        return None
    
    def find_all(self, seg_id: str) -> list[Segment]:
        """Find all segments with given ID in direct segments."""
        return [seg for seg in self.segments if seg.segment_id == seg_id]
    
    def find_loop(self, loop_id: str) -> list['Loop']:
        """Recursively find all child loops with given ID."""
        result = []
        for child in self.children:
            if child.loop_id == loop_id:
                result.append(child)
            result.extend(child.find_loop(loop_id))
        return result


class EnvelopeMeta(BaseModel):
    """ISA/GS/ST envelope metadata."""
    
    isa_control_number: str
    gs_control_number: str
    st_control_number: str
    sender_id: str
    receiver_id: str
    interchange_date: str
    interchange_time: str
    version: str
    transaction_type: str
    
    model_config = ConfigDict(populate_by_name=True)


class ParsedEDI(BaseModel):
    """Complete parsed EDI transaction."""
    
    envelope: EnvelopeMeta
    loops: list[Loop] = Field(default_factory=list)
    raw: str
    
    model_config = ConfigDict(populate_by_name=True)


class ValidationError(BaseModel):
    """Represents a single validation error."""
    
    code: str
    severity: Literal['error', 'warning', 'info']
    segment: str
    element: str | None = None
    loop: str | None = None
    position: int
    message: str
    
    model_config = ConfigDict(populate_by_name=True)


class ValidationResult(BaseModel):
    """Result of validation including parsed data and errors."""
    
    parsed: ParsedEDI
    errors: list[ValidationError] = Field(default_factory=list)
    
    model_config = ConfigDict(populate_by_name=True)
    
    @property
    def is_valid(self) -> bool:
        """True if no errors with severity == 'error'."""
        return not any(err.severity == 'error' for err in self.errors)
    
    @property
    def error_count(self) -> int:
        """Count of errors with severity == 'error'."""
        return sum(1 for err in self.errors if err.severity == 'error')
    
    @property
    def warning_count(self) -> int:
        """Count of errors with severity == 'warning'."""
        return sum(1 for err in self.errors if err.severity == 'warning')
