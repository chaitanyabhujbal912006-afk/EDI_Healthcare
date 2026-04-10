from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import EnvelopeMeta, LoopNode, ParseResult, Segment, TransactionType


@dataclass
class Delimiters:
    element: str = "*"
    segment: str = "~"
    component: str = ":"


def _split_segments(content: str, delimiters: Delimiters) -> list[str]:
    text = content.replace("\r", "").replace("\n", "")
    return [seg for seg in text.split(delimiters.segment) if seg.strip()]


def detect_delimiters(content: str) -> Delimiters:
    if len(content) < 106:
        return Delimiters()
    if not content.startswith("ISA"):
        return Delimiters()
    element = content[3]
    segment = content[105] if len(content) > 105 else "~"
    component = ":"
    return Delimiters(element=element, segment=segment, component=component)


def parse_segments(content: str) -> tuple[list[Segment], Delimiters]:
    delimiters = detect_delimiters(content)
    raw_segments = _split_segments(content, delimiters)
    segments: list[Segment] = []

    for i, raw in enumerate(raw_segments, start=1):
        parts = raw.split(delimiters.element)
        segment_id = parts[0].strip()
        elements = [p.strip() for p in parts[1:]]
        if segment_id:
            segments.append(Segment(id=segment_id, elements=elements, line_number=i))

    return segments, delimiters


def detect_transaction_type(segments: list[Segment]) -> TransactionType:
    st = next((s for s in segments if s.id == "ST"), None)
    bht = next((s for s in segments if s.id == "BHT"), None)

    if not st or not st.elements:
        return "UNKNOWN"

    st01 = st.elements[0]
    if st01 == "835":
        return "835"
    if st01 == "834":
        return "834"
    if st01 == "837":
        # 005010X222A1 = 837P; 005010X223A2 = 837I (common guides)
        guide = st.elements[2] if len(st.elements) > 2 else ""
        bht06 = bht.elements[5] if bht and len(bht.elements) > 5 else ""
        if "X223" in guide or bht06 == "RP":
            return "837I"
        return "837P"
    return "UNKNOWN"


def extract_envelope(segments: list[Segment]) -> EnvelopeMeta:
    isa = next((s for s in segments if s.id == "ISA"), None)
    gs = next((s for s in segments if s.id == "GS"), None)
    ge = next((s for s in segments if s.id == "GE"), None)

    return EnvelopeMeta(
        sender_id=(isa.elements[5] if isa and len(isa.elements) > 5 else None),
        receiver_id=(isa.elements[7] if isa and len(isa.elements) > 7 else None),
        interchange_date=(isa.elements[8] if isa and len(isa.elements) > 8 else None),
        gs_functional_group=(gs.elements[0] if gs and gs.elements else None),
        transaction_set_count=int(ge.elements[0]) if ge and ge.elements and ge.elements[0].isdigit() else 1,
        control_number=(isa.elements[12] if isa and len(isa.elements) > 12 else None),
    )


def _create_loop_name(tx_type: TransactionType, segment: Segment, current_count: int) -> tuple[str, str]:
    if segment.id == "HL":
        code = segment.elements[2] if len(segment.elements) > 2 else str(current_count)
        return f"HL-{code}", f"Hierarchical Level {code}"
    if tx_type == "835" and segment.id == "CLP":
        claim_id = segment.elements[0] if segment.elements else str(current_count)
        return f"CLP-{claim_id}", f"Claim Payment Loop {claim_id}"
    if tx_type == "834" and segment.id == "INS":
        maint = segment.elements[0] if segment.elements else "UNK"
        return f"MEM-{current_count}", f"Member Loop {maint}"
    return f"LOOP-{current_count}", f"Loop {current_count}"


def build_loop_tree(segments: list[Segment], tx_type: TransactionType) -> LoopNode:
    root = LoopNode(name="ROOT", label="Transaction")
    current = LoopNode(name="HEADER", label="Header")
    root.children.append(current)
    loop_count = 0

    for seg in segments:
        opens_loop = seg.id in {"HL", "CLP", "INS"}
        if tx_type == "837P" or tx_type == "837I":
            opens_loop = seg.id in {"HL", "LX"}

        if opens_loop:
            loop_count += 1
            name, label = _create_loop_name(tx_type, seg, loop_count)
            current = LoopNode(name=name, label=label)
            current.segments.append(seg)
            root.children.append(current)
        else:
            current.segments.append(seg)

    return root


def parse_x12(content: str) -> ParseResult:
    segments, delimiters = parse_segments(content)
    tx_type = detect_transaction_type(segments)
    envelope = extract_envelope(segments)
    tree = build_loop_tree(segments, tx_type)

    return ParseResult(
        transaction_type=tx_type,
        delimiters={
            "element": delimiters.element,
            "segment": delimiters.segment,
            "component": delimiters.component,
        },
        envelope=envelope,
        segments=segments,
        loop_tree=tree,
    )


def to_segment_text(segments: list[Segment], element_sep: str = "*", segment_sep: str = "~") -> str:
    built: list[str] = []
    for seg in segments:
        built.append(element_sep.join([seg.id, *seg.elements]))
    return segment_sep.join(built) + segment_sep


def extract_claim_amounts_for_837(segments: list[Segment]) -> tuple[float, float]:
    claim_total = 0.0
    svc_total = 0.0

    for seg in segments:
        if seg.id == "CLM" and len(seg.elements) > 1:
            claim_total += _to_float(seg.elements[1])
        if seg.id in {"SV1", "SV2"} and len(seg.elements) > 1:
            svc_total += _to_float(seg.elements[1])

    return claim_total, svc_total


def _to_float(value: str) -> float:
    clean = re.sub(r"[^0-9.\-]", "", value or "")
    if not clean:
        return 0.0
    try:
        return float(clean)
    except ValueError:
        return 0.0

