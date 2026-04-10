from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


TransactionType = Literal["837P", "837I", "835", "834", "UNKNOWN"]


class Segment(BaseModel):
    id: str
    elements: list[str]
    line_number: int


class LoopNode(BaseModel):
    name: str
    label: str
    segments: list[Segment] = Field(default_factory=list)
    children: list["LoopNode"] = Field(default_factory=list)


class EnvelopeMeta(BaseModel):
    sender_id: str | None = None
    receiver_id: str | None = None
    interchange_date: str | None = None
    gs_functional_group: str | None = None
    transaction_set_count: int = 0
    control_number: str | None = None


class ParseResult(BaseModel):
    transaction_type: TransactionType
    delimiters: dict[str, str]
    envelope: EnvelopeMeta
    segments: list[Segment]
    loop_tree: LoopNode


class ValidationIssue(BaseModel):
    code: str
    severity: Literal["error", "warning"]
    message: str
    loop_location: str
    segment_id: str
    element_position: int | None = None
    current_value: str | None = None
    suggested_value: str | None = None


class ValidationResult(BaseModel):
    valid: bool
    issues: list[ValidationIssue]


class ParsedFileReport(BaseModel):
    filename: str
    parse_result: ParseResult
    validation_result: ValidationResult


class UploadResponse(BaseModel):
    report: ParsedFileReport
    remittance_summary: list[dict[str, Any]] = Field(default_factory=list)
    enrollment_summary: list[dict[str, Any]] = Field(default_factory=list)


class ChatRequest(BaseModel):
    question: str
    context: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    answer: str


class ReconcileRequest(BaseModel):
    edi_837: str
    edi_835: str


class DeltaRequest(BaseModel):
    old_834: str
    new_834: str


class EligibilityRequest(BaseModel):
    edi_834: str
    edi_837: str


class ParseRequest(BaseModel):
    content: str


class BatchResult(BaseModel):
    total_files: int
    passed: int
    failed: int
    reports: list[ParsedFileReport]


LoopNode.model_rebuild()

