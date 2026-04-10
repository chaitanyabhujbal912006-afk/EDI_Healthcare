"""
Main parse function - entry point for EDI parsing.
"""

from pathlib import Path
from validedi.engine.models import ParsedEDI, EnvelopeMeta, Loop
from validedi.engine.detector import detect
from validedi.engine.tokenizer import tokenize
from validedi.engine.config_loader import get_config
from validedi.engine.loop_builder import build_loops as build_loop_hierarchy
from validedi.utils.exceptions import EDIParseError


def parse(source: str | Path) -> ParsedEDI:
    """
    Parse EDI file or string into structured ParsedEDI object.
    
    This is the fast path - it does NOT run validation rules.
    
    Args:
        source: Either a file path (str/Path) or raw EDI string
                - If it's a valid file path, reads the file
                - Otherwise treats it as raw EDI content
                - Supported file extensions: .edi, .x12, .dat, .txt (case-insensitive)
        
    Returns:
        ParsedEDI object with envelope and loop hierarchy
        
    Raises:
        EDIParseError: If EDI cannot be parsed
        UnsupportedTransactionError: If transaction type not supported
        FileNotFoundError: If file path doesn't exist
    
    Examples:
        # Parse from EDI file
        result = parse('claim.edi')
        
        # Parse from X12 file
        result = parse('claim.x12')
        
        # Parse from DAT file
        result = parse('claim.dat')
        
        # Parse from path
        result = parse('/path/to/file.edi')
        result = parse(Path('claim.x12'))
        
        # Parse from raw string
        result = parse('ISA*00*...')
    """
    # Read file if source is a path
    raw = _read_source(source)
    
    # Detect delimiters and transaction type
    delimiters = detect(raw)
    
    # Tokenize into flat segment list
    segments = tokenize(raw, delimiters)
    
    # Extract envelope metadata
    envelope = _extract_envelope(segments, delimiters.transaction_type)
    
    # Load configuration for this transaction type
    config = get_config(delimiters.transaction_type)
    
    # Filter out envelope segments for loop building
    data_segments = [
        seg for seg in segments
        if seg.segment_id not in ['ISA', 'IEA', 'GS', 'GE', 'ST', 'SE']
    ]
    
    # Build loop hierarchy using configuration
    loops = build_loop_hierarchy(data_segments, config)
    
    return ParsedEDI(
        envelope=envelope,
        loops=loops,
        raw=raw
    )


def _read_source(source: str | Path) -> str:
    """
    Read EDI content from file or return as-is if it's raw content.
    
    Args:
        source: File path or raw EDI string
        
    Returns:
        Raw EDI string
        
    Raises:
        FileNotFoundError: If file path doesn't exist
    """
    # Convert to Path if string
    if isinstance(source, str):
        # Check if it looks like a file path
        if _is_file_path(source):
            source = Path(source)
        else:
            # Treat as raw EDI content
            return source
    
    # Read from file
    if isinstance(source, Path):
        if not source.exists():
            raise FileNotFoundError(f"EDI file not found: {source}")
        
        with open(source, 'r', encoding='utf-8') as f:
            return f.read()
    
    return source


def _is_file_path(s: str) -> bool:
    """
    Check if string looks like a file path.
    
    Heuristic: If it contains path separators or file extensions,
    or if the file exists, treat it as a path.
    
    Supported file extensions: .edi, .x12, .dat, .txt (case-insensitive)
    """
    # Check if file exists
    if Path(s).exists():
        return True
    
    # Check for EDI-related file extensions (case-insensitive)
    lower_s = s.lower()
    if lower_s.endswith(('.edi', '.x12', '.dat', '.txt')):
        return True
    
    # Check for path separators
    if '/' in s or '\\' in s:
        return True
    
    # If it starts with ISA, it's probably raw EDI content
    if s.strip().startswith('ISA'):
        return False
    
    # Default: if it's short and has no newlines, might be a filename
    if len(s) < 200 and '\n' not in s and '~' not in s:
        return True
    
    return False


def _extract_envelope(segments: list, transaction_type: str) -> EnvelopeMeta:
    """Extract ISA/GS/ST envelope metadata."""
    isa = None
    gs = None
    st = None
    
    for segment in segments:
        if segment.segment_id == 'ISA':
            isa = segment
        elif segment.segment_id == 'GS':
            gs = segment
        elif segment.segment_id == 'ST':
            st = segment
            break
    
    if not isa or not gs or not st:
        raise EDIParseError('Missing required envelope segments (ISA/GS/ST)')
    
    return EnvelopeMeta(
        isa_control_number=isa.get_value(13),
        gs_control_number=gs.get_value(6),
        st_control_number=st.get_value(2),
        sender_id=isa.get_value(6),
        receiver_id=isa.get_value(8),
        interchange_date=isa.get_value(9),
        interchange_time=isa.get_value(10),
        version=gs.get_value(8),
        transaction_type=transaction_type
    )


