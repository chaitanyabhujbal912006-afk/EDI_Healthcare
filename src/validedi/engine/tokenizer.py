"""
EDI tokenizer - converts raw EDI string to flat list of Segment objects.
"""

from validedi.engine.models import Segment, Element
from validedi.engine.detector import DelimiterSet


def tokenize(raw: str, delimiters: DelimiterSet) -> list[Segment]:
    """
    Tokenize raw EDI string into flat list of Segment objects.
    
    Args:
        raw: Raw EDI string
        delimiters: Detected delimiter set
        
    Returns:
        Flat list of Segment objects in order
    """
    segments = []
    raw_segments = raw.split(delimiters.segment_sep)
    
    position = 0
    for raw_segment in raw_segments:
        raw_segment = raw_segment.strip()
        if not raw_segment:
            continue
        
        # Split by element separator
        parts = raw_segment.split(delimiters.element_sep)
        if not parts:
            continue
        
        segment_id = parts[0].strip()
        if not segment_id:
            continue
        
        # Create Element objects for each element (skip segment_id)
        elements = []
        for element_str in parts[1:]:
            # Split by sub-element separator for composite elements
            components = element_str.split(delimiters.sub_sep) if delimiters.sub_sep in element_str else [element_str]
            elements.append(Element(
                raw=element_str,
                components=components
            ))
        
        segments.append(Segment(
            segment_id=segment_id,
            elements=elements,
            position=position
        ))
        position += 1
    
    return segments
