from __future__ import annotations

import re
from typing import Literal

from app.models import (
    EnvelopeMeta,
    LoopNode,
    ParseResult,
    Segment,
    TransactionType,
    ValidationIssue,
    ValidationResult,
)
from validedi.engine.detector import DelimiterSet, detect
from validedi.engine.models import (
    ParsedEDI as ValidediParsedEDI,
)
from validedi.engine.models import (
    Segment as ValidediSegment,
)
from validedi.engine.models import (
    ValidationError as ValidediValidationError,
)
from validedi.engine.models import (
    ValidationResult as ValidediValidationResult,
)
from validedi.engine.parser import parse as validedi_parse
from validedi.engine.tokenizer import tokenize
from validedi.engine.validator import validate as validedi_validate
from validedi.utils.exceptions import EDIParseError, UnsupportedTransactionError


def _map_transaction_type(validedi_type: str | None) -> TransactionType:
    if not validedi_type:
        return "UNKNOWN"
    norm = validedi_type.strip().upper()
    if norm in {"837P", "837I", "835", "834"}:
        return norm  # type: ignore[return-value]
    if norm == "837":
        return "837P"
    return "UNKNOWN"


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
        if tx_type in {"837P", "837I"}:
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


def validedi_segment_to_model(seg: ValidediSegment) -> Segment:
    """Convert a validedi Segment to the backend Segment model."""
    elements = [e.raw for e in seg.elements]
    return Segment(id=seg.segment_id, elements=elements, line_number=seg.position + 1)


def validedi_parsed_to_model(
    parsed: ValidediParsedEDI, delimiters: DelimiterSet | None = None
) -> ParseResult:
    """Convert a validedi ParsedEDI to the backend ParseResult model."""
    tx_type = _map_transaction_type(parsed.envelope.transaction_type)

    if delimiters is None:
        try:
            delimiters = detect(parsed.raw)
        except (EDIParseError, ValueError):
            delimiters = DelimiterSet(
                element_sep="*",
                segment_sep="~",
                sub_sep=":",
                transaction_type=parsed.envelope.transaction_type or "unknown",
            )

    tokenized_segments = tokenize(parsed.raw, delimiters)
    model_segments = [validedi_segment_to_model(s) for s in tokenized_segments]

    # Find GS and GE for envelope metadata
    gs_seg = next((s for s in model_segments if s.id == "GS"), None)
    ge_seg = next((s for s in model_segments if s.id == "GE"), None)

    tx_set_count = 1
    if ge_seg and ge_seg.elements and ge_seg.elements[0].isdigit():
        tx_set_count = int(ge_seg.elements[0])

    envelope = EnvelopeMeta(
        sender_id=parsed.envelope.sender_id,
        receiver_id=parsed.envelope.receiver_id,
        interchange_date=parsed.envelope.interchange_date,
        gs_functional_group=gs_seg.elements[0] if (gs_seg and gs_seg.elements) else None,
        transaction_set_count=tx_set_count,
        control_number=parsed.envelope.isa_control_number,
    )

    tree = build_loop_tree(model_segments, tx_type)

    return ParseResult(
        transaction_type=tx_type,
        delimiters={
            "element": delimiters.element_sep,
            "segment": delimiters.segment_sep,
            "component": delimiters.sub_sep,
        },
        envelope=envelope,
        segments=model_segments,
        loop_tree=tree,
    )


def _extract_element_position(element_str: str | None) -> int | None:
    if not element_str:
        return None
    m = re.search(r"(\d+)$", element_str)
    return int(m.group(1)) if m else None


LEGACY_CODE_MAP = {
    "CNT-001": "SE_COUNT_MISMATCH",
    "CHARGE_TOTAL_CHECK": "CLM_SUM_MISMATCH",
    "CHARGE_TOTAL_CHECK_I": "CLM_SUM_MISMATCH",
    "CLP_PAID_VS_BILLED": "CLP_RECON_FAIL",
    "DUPLICATE_MEMBER_CHECK": "MEMBER_DUPLICATE",
    "834-007": "MEMBER_DUPLICATE",
}


def validedi_error_to_issue(error: ValidediValidationError) -> ValidationIssue:
    """Convert a single validedi ValidationError to a backend ValidationIssue."""
    sev: Literal["error", "warning"] = "error" if error.severity == "error" else "warning"
    pos = _extract_element_position(error.element)

    # Clean segment id
    seg_id = error.segment
    if not seg_id and error.element:
        m = re.match(r"^([A-Z0-9]+)", error.element)
        if m:
            seg_id = m.group(1)
    if not seg_id:
        seg_id = "UNKNOWN"

    mapped_code = LEGACY_CODE_MAP.get(error.code, error.code)

    return ValidationIssue(
        code=mapped_code,
        severity=sev,
        message=error.message,
        loop_location=error.loop or "ROOT",
        segment_id=seg_id,
        element_position=pos,
        current_value=None,
        suggested_value=None,
    )


def validedi_validation_to_model(
    validedi_res: ValidediValidationResult,
) -> ValidationResult:
    """Convert a validedi ValidationResult to backend ValidationResult."""
    issues = [validedi_error_to_issue(err) for err in validedi_res.errors]
    is_valid = validedi_res.is_valid and not any(i.severity == "error" for i in issues)
    return ValidationResult(valid=is_valid, issues=issues)


def parse_edi_content(content: str) -> ParseResult:
    """Parse EDI string using validedi with graceful fallback for unknown/malformed content."""
    try:
        delimiters = detect(content)
        parsed = validedi_parse(content)
        return validedi_parsed_to_model(parsed, delimiters)
    except UnsupportedTransactionError:
        # Detected delimiters and segments, but transaction type is unsupported
        try:
            delims = detect(content)
        except (EDIParseError, ValueError):
            delims = DelimiterSet(element_sep="*", segment_sep="~", sub_sep=":", transaction_type="unknown")
        tokenized = tokenize(content, delims)
        model_segments = [validedi_segment_to_model(s) for s in tokenized]
        envelope = EnvelopeMeta()
        tree = build_loop_tree(model_segments, "UNKNOWN")
        return ParseResult(
            transaction_type="UNKNOWN",
            delimiters={
                "element": delims.element_sep,
                "segment": delims.segment_sep,
                "component": delims.sub_sep,
            },
            envelope=envelope,
            segments=model_segments,
            loop_tree=tree,
        )
    except EDIParseError:
        # Fallback to minimal parse result
        return ParseResult(
            transaction_type="UNKNOWN",
            delimiters={"element": "*", "segment": "~", "component": ":"},
            envelope=EnvelopeMeta(),
            segments=[],
            loop_tree=LoopNode(name="ROOT", label="Transaction"),
        )


def validate_edi_content(
    source: str | ValidediParsedEDI | ParseResult,
) -> ValidationResult:
    """Validate EDI using validedi, converting the result to backend ValidationResult."""
    if isinstance(source, ParseResult):
        if source.transaction_type == "UNKNOWN":
            return ValidationResult(
                valid=False,
                issues=[
                    ValidationIssue(
                        code="TXN_UNKNOWN",
                        severity="error",
                        message="Unable to detect transaction type from ST segment.",
                        loop_location="ROOT",
                        segment_id="ST",
                    )
                ],
            )
        # Reconstruct segment text
        content = to_segment_text(
            source.segments,
            element_sep=source.delimiters.get("element", "*"),
            segment_sep=source.delimiters.get("segment", "~"),
        )
        return validate_edi_content(content)

    if isinstance(source, str):
        try:
            detect(source)
        except UnsupportedTransactionError:
            return ValidationResult(
                valid=False,
                issues=[
                    ValidationIssue(
                        code="TXN_UNKNOWN",
                        severity="error",
                        message="Unable to detect transaction type from ST segment.",
                        loop_location="ROOT",
                        segment_id="ST",
                    )
                ],
            )
        except EDIParseError as exc:
            return ValidationResult(
                valid=False,
                issues=[
                    ValidationIssue(
                        code="PARSE_ERROR",
                        severity="error",
                        message=str(exc),
                        loop_location="ROOT",
                        segment_id="ISA",
                    )
                ],
            )

    vres = validedi_validate(source)
    return validedi_validation_to_model(vres)


def to_segment_text(
    segments: list[Segment], element_sep: str = "*", segment_sep: str = "~"
) -> str:
    """Reconstruct EDI text from a list of Segment models."""
    built: list[str] = []
    for seg in segments:
        built.append(element_sep.join([seg.id, *seg.elements]))
    return segment_sep.join(built) + segment_sep


def extract_claim_amounts_for_837(segments: list[Segment]) -> tuple[float, float]:
    """Sum total billed charges and total line item service charges."""
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
