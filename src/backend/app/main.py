from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.models import (
    BatchResult,
    ChatRequest,
    ChatResponse,
    DeltaRequest,
    EligibilityRequest,
    ParseRequest,
    ParsedFileReport,
    ReconcileRequest,
    UploadResponse,
)
from app.parser.x12_parser import parse_x12, to_segment_text
from app.services.chat import ask_huggingface
from app.services.exports import csv_bytes, error_report_pdf_bytes, json_bytes
from app.services.summaries import build_834_summary, build_835_summary, build_family_grouping
from app.validation.rules import validate

app = FastAPI(title="EdiPro Healthcare EDI Parser API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


STITCH_DIR = Path(__file__).resolve().parents[2] / "stitch"
if STITCH_DIR.exists():
    app.mount("/stitch", StaticFiles(directory=STITCH_DIR, html=True), name="stitch")


@app.get("/")
def frontend_home() -> RedirectResponse:
    if STITCH_DIR.exists():
        return RedirectResponse(url="/stitch/dashboard_sleek/code.html", status_code=307)
    return RedirectResponse(url="/api/health", status_code=307)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/parse")
def parse_raw(request: ParseRequest) -> dict[str, Any]:
    parsed = parse_x12(request.content)
    validation = validate(parsed)
    return {
        "parse_result": parsed.model_dump(),
        "validation_result": validation.model_dump(),
    }


MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_BATCH_SIZE = 100 * 1024 * 1024  # 100 MB


@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds maximum limit of 50 MB.")

    content = file_bytes.decode("utf-8", errors="ignore")
    parsed = parse_x12(content)
    validation = validate(parsed)

    safe_filename = Path(file.filename or "uploaded.edi").name

    report = ParsedFileReport(
        filename=safe_filename,
        parse_result=parsed,
        validation_result=validation,
    )

    remittance_summary = build_835_summary(parsed.segments) if parsed.transaction_type == "835" else []
    enrollment_summary = build_834_summary(parsed.segments) if parsed.transaction_type == "834" else []

    return UploadResponse(
        report=report,
        remittance_summary=remittance_summary,
        enrollment_summary=enrollment_summary,
    )


@app.post("/api/batch", response_model=BatchResult)
async def batch_upload(file: UploadFile = File(...)) -> BatchResult:
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Please upload a ZIP file for batch processing.")

    content = await file.read()
    if len(content) > MAX_BATCH_SIZE:
        raise HTTPException(status_code=413, detail="Batch ZIP file size exceeds maximum limit of 100 MB.")

    zip_buffer = io.BytesIO(content)
    reports: list[ParsedFileReport] = []

    with zipfile.ZipFile(zip_buffer) as zf:
        for name in zf.namelist():
            safe_name = Path(name).name
            if not safe_name or not safe_name.lower().endswith((".edi", ".txt", ".dat", ".x12")):
                continue
            data = zf.read(name).decode("utf-8", errors="ignore")
            parsed = parse_x12(data)
            validation = validate(parsed)
            reports.append(
                ParsedFileReport(filename=safe_name, parse_result=parsed, validation_result=validation)
            )

    failed = sum(1 for r in reports if not r.validation_result.valid)
    passed = len(reports) - failed

    return BatchResult(total_files=len(reports), passed=passed, failed=failed, reports=reports)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    answer = await ask_huggingface(request.question, request.context)
    return ChatResponse(answer=answer)


@app.post("/api/reconcile/835-837")
def reconcile_835_837(request: ReconcileRequest) -> dict[str, Any]:
    p837 = parse_x12(request.edi_837)
    p835 = parse_x12(request.edi_835)

    claims_837: dict[str, float] = {}
    for seg in p837.segments:
        if seg.id == "CLM" and len(seg.elements) > 1:
            claims_837[seg.elements[0]] = _to_float(seg.elements[1])

    claims_835: dict[str, dict[str, float]] = {}
    for seg in p835.segments:
        if seg.id == "CLP" and len(seg.elements) > 3:
            claims_835[seg.elements[0]] = {
                "billed": _to_float(seg.elements[2]),
                "paid": _to_float(seg.elements[3]),
            }

    rows = []
    for claim_id, billed_837 in claims_837.items():
        from_835 = claims_835.get(claim_id, {"billed": 0.0, "paid": 0.0})
        rows.append(
            {
                "claim_id": claim_id,
                "837_billed": billed_837,
                "835_billed": from_835["billed"],
                "835_paid": from_835["paid"],
                "variance": round(billed_837 - from_835["paid"], 2),
            }
        )

    return {"rows": rows, "matched": len([r for r in rows if r["835_paid"] > 0])}


@app.post("/api/delta/834")
def delta_834(request: DeltaRequest) -> dict[str, Any]:
    old_summary = build_834_summary(parse_x12(request.old_834).segments)
    new_summary = build_834_summary(parse_x12(request.new_834).segments)

    old_map = {m.get("member_id", ""): m for m in old_summary if m.get("member_id")}
    new_map = {m.get("member_id", ""): m for m in new_summary if m.get("member_id")}

    added = [m for mid, m in new_map.items() if mid not in old_map]
    terminated = [m for mid, m in old_map.items() if mid not in new_map]

    changed = []
    for mid in set(old_map.keys()) & set(new_map.keys()):
        if old_map[mid] != new_map[mid]:
            changed.append({"member_id": mid, "from": old_map[mid], "to": new_map[mid]})

    return {"added": added, "terminated": terminated, "changed": changed}


@app.post("/api/eligibility/834-837")
def eligibility_check(request: EligibilityRequest) -> dict[str, Any]:
    members = build_834_summary(parse_x12(request.edi_834).segments)
    member_ids = {m.get("member_id") for m in members if m.get("member_id")}

    parsed_837 = parse_x12(request.edi_837)
    claims: list[dict[str, str]] = []
    current_claim = ""

    for seg in parsed_837.segments:
        if seg.id == "CLM" and seg.elements:
            current_claim = seg.elements[0]
        if seg.id == "REF" and len(seg.elements) > 1 and seg.elements[0] in {"SY", "1W", "Y4"}:
            claims.append({"claim_id": current_claim, "member_id": seg.elements[1]})

    ineligible = [c for c in claims if c["member_id"] not in member_ids]
    return {"total_claims_with_member_ref": len(claims), "ineligible_claims": ineligible}


@app.post("/api/export/json")
def export_json(payload: dict[str, Any]) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(json_bytes(payload)),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=parsed.json"},
    )


@app.post("/api/export/errors-pdf")
def export_errors_pdf(payload: dict[str, Any]) -> StreamingResponse:
    issues = payload.get("issues", [])
    return StreamingResponse(
        io.BytesIO(error_report_pdf_bytes(issues)),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=validation-report.pdf"},
    )


@app.post("/api/export/members-csv")
def export_members_csv(payload: dict[str, Any]) -> StreamingResponse:
    rows = payload.get("rows", [])
    return StreamingResponse(
        io.BytesIO(csv_bytes(rows)),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=members.csv"},
    )


@app.post("/api/export/corrected-edi")
def export_corrected_edi(payload: dict[str, Any]) -> StreamingResponse:
    segments = payload.get("segments", [])
    try:
        text = to_segment_text([_segment_from_dict(s) for s in segments])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid segment payload: {exc}")

    return StreamingResponse(
        io.BytesIO(text.encode("utf-8")),
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=corrected.edi"},
    )


@app.post("/api/834/family-grouping")
def family_grouping(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows", [])
    return {"groups": build_family_grouping(rows)}


def _segment_from_dict(data: dict[str, Any]) -> Any:
    from app.models import Segment

    return Segment(
        id=data.get("id", ""),
        elements=list(data.get("elements", [])),
        line_number=int(data.get("line_number", 0)),
    )


def _to_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0

