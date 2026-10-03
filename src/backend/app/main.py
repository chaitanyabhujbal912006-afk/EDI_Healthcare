import asyncio
import hashlib
import io
import json
import logging
import os
import platform
import sys
import time
import uuid
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt
from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.adapters import (
    get_total_rules_count,
    parse_edi_content,
    to_segment_text,
    validate_edi_content,
)
from app.config import AuthSettings
from app.models import (
    BatchResult,
    ChatRequest,
    ChatResponse,
    DeltaRequest,
    EligibilityRequest,
    ParsedFileReport,
    ParseRequest,
    ReconcileRequest,
    UploadResponse,
)
from app.security import AuthIdentity, RateLimiter, require_role
from app.services.chat import ask_huggingface
from app.services.exports import csv_bytes, error_report_pdf_bytes, json_bytes, tsv_bytes
from app.services.summaries import (
    build_834_summary,
    build_835_summary,
    build_837i_summary,
    build_family_grouping,
)

_SERVER_START_TIME: datetime = datetime.now(timezone.utc)
_is_shutting_down = False


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _is_shutting_down
    _is_shutting_down = False
    yield
    _is_shutting_down = True


app = FastAPI(
    title="EdiPro Healthcare EDI Parser API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.logging_config import PHIRedactionFilter, request_id_ctx, setup_logging
from app.metrics import (
    REQUEST_COUNT,
    REQUEST_LATENCY,
    UPLOAD_BYTES,
    VALIDATION_OUTCOMES,
    get_route_template,
    metrics_endpoint,
)

setup_logging()

audit_logger = logging.getLogger("edipro.audit")
if not audit_logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _handler.addFilter(PHIRedactionFilter())
    audit_logger.addHandler(_handler)
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False
else:
    for h in audit_logger.handlers:
        h.addFilter(PHIRedactionFilter())


@app.middleware("http")
async def add_security_headers(request: Request, call_next: Any) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    return response


_upload_semaphore: asyncio.Semaphore | None = None


def get_upload_semaphore() -> asyncio.Semaphore:
    global _upload_semaphore
    if _upload_semaphore is None:
        max_concurrent = int(os.getenv("MAX_CONCURRENT_UPLOADS", "10"))
        _upload_semaphore = asyncio.Semaphore(max_concurrent)
    return _upload_semaphore


def set_upload_semaphore(limit: int) -> asyncio.Semaphore:
    global _upload_semaphore
    _upload_semaphore = asyncio.Semaphore(limit)
    return _upload_semaphore


@app.middleware("http")
async def request_timeout_middleware(request: Request, call_next: Any) -> Response:
    timeout_sec = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
    try:
        return await asyncio.wait_for(call_next(request), timeout=timeout_sec)
    except asyncio.TimeoutError:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=504,
            content={"detail": f"Request processing timed out after {timeout_sec}s."},
        )


@app.middleware("http")
async def heavy_request_concurrency_middleware(request: Request, call_next: Any) -> Response:
    if request.url.path in ("/api/upload", "/api/batch"):
        sem = get_upload_semaphore()
        async with sem:
            return await call_next(request)
    return await call_next(request)


@app.middleware("http")
async def prometheus_metrics_middleware(request: Request, call_next: Any) -> Response:
    start_time = time.perf_counter()
    status_code = "500"
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        return response
    finally:
        duration_sec = time.perf_counter() - start_time
        route_tmpl = get_route_template(request)
        REQUEST_COUNT.labels(route=route_tmpl, method=request.method, status=status_code).inc()
        REQUEST_LATENCY.labels(route=route_tmpl, method=request.method, status=status_code).observe(duration_sec)


rate_limiter = RateLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "200")),
    window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next: Any) -> Response:
    if request.url.path.startswith("/api/") and request.url.path not in ("/api/health", "/api/ready"):
        try:
            rate_limiter.check(request)
        except HTTPException as exc:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=dict(exc.headers or {}),
            )
    return await call_next(request)


@app.middleware("http")
async def audit_log_middleware(request: Request, call_next: Any) -> Response:
    # Skip non-api requests and /api/health
    if not request.url.path.startswith("/api/") or request.url.path == "/api/health":
        return await call_next(request)

    start_time = time.perf_counter()
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = request_id_ctx.set(request_id)
    bytes_in = int(request.headers.get("content-length") or 0)

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "subject": "anonymous",
            "role": "none",
            "method": request.method,
            "path": request.url.path,
            "status": 500,
            "duration_ms": duration_ms,
            "bytes_in": bytes_in,
            "file_count": 0,
            "transaction_type": None,
            "outcome": "denied",
        }
        audit_logger.info(json.dumps(record))
        raise
    finally:
        request_id_ctx.reset(token)

    response.headers["X-Request-ID"] = request_id
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    identity: AuthIdentity | None = getattr(request.state, "auth_identity", None)
    if identity:
        subject = identity.subject
        role = identity.role
    else:
        auth_hdr = request.headers.get("authorization", "")
        key_hdr = request.headers.get("x-api-key", "")
        if key_hdr:
            subject = hashlib.sha256(key_hdr.strip().encode("utf-8")).hexdigest()[:8]
        elif auth_hdr.lower().startswith("bearer "):
            try:
                unverified = jwt.decode(auth_hdr[7:].strip(), options={"verify_signature": False})
                subject = str(unverified.get("sub", "anonymous"))
            except Exception:  # noqa: BLE001
                subject = "anonymous"
        else:
            subject = "anonymous"
        role = "none"

    file_count = getattr(request.state, "file_count", 0)
    tx_type = getattr(request.state, "transaction_type", None)
    outcome = "denied" if response.status_code in (401, 403, 503) else "allowed"

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "subject": subject,
        "role": role,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": duration_ms,
        "bytes_in": bytes_in,
        "file_count": file_count,
        "transaction_type": tx_type,
        "outcome": outcome,
    }
    audit_logger.info(json.dumps(record))
    response.headers["X-Request-ID"] = request_id
    return response


STITCH_DIR = Path(__file__).resolve().parents[2] / "stitch"
DIST_DIR = STITCH_DIR / "dist"
if DIST_DIR.exists():
    app.mount("/stitch", StaticFiles(directory=DIST_DIR, html=True), name="stitch")
    if (DIST_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")
elif STITCH_DIR.exists():
    app.mount("/stitch", StaticFiles(directory=STITCH_DIR, html=True), name="stitch")


@app.get("/")
def frontend_home() -> RedirectResponse:
    if DIST_DIR.exists() or STITCH_DIR.exists():
        return RedirectResponse(url="/stitch/index.html", status_code=307)
    return RedirectResponse(url="/api/health", status_code=307)



@app.get("/metrics")
def get_metrics(request: Request) -> Response:
    return metrics_endpoint(request)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/ready")
def readiness_check() -> dict[str, Any]:
    if _is_shutting_down:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "shutting_down", "ready": False},
        )

    try:
        from validedi.engine.config_loader import ConfigLoader

        loader = ConfigLoader()
        loaded = []
        for txn in ("837p", "837i", "835", "834"):
            cfg = loader.get_config(txn)
            if not cfg or not hasattr(cfg, "rules"):
                raise ValueError(f"Config for {txn} missing or invalid")
            loaded.append(txn)

        return {
            "status": "ready",
            "ready": True,
            "validation_config": "loaded",
            "transactions": loaded,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "ready": False, "error": str(exc)},
        ) from exc


@app.get("/api/auth/config")
def auth_config(http_request: Request) -> dict[str, Any]:
    http_request.state.file_count = 0
    settings = AuthSettings.from_env()
    oidc_ready = bool(settings.oidc_issuer and settings.oidc_jwks_url)
    auth_url = settings.oidc_authorize_url or (
        f"{settings.oidc_issuer.rstrip('/')}/protocol/openid-connect/auth"
        if settings.oidc_issuer
        else None
    )
    token_url = settings.oidc_token_url or (
        f"{settings.oidc_issuer.rstrip('/')}/protocol/openid-connect/token"
        if settings.oidc_issuer
        else None
    )
    return {
        "oidc_configured": oidc_ready,
        "issuer": settings.oidc_issuer,
        "audience": settings.oidc_audience,
        "client_id": settings.oidc_client_id or "edipro-public-client",
        "authorize_url": auth_url,
        "token_url": token_url,
    }


@app.get("/api/health/detailed")
def health_detailed(_identity: AuthIdentity = Depends(require_role("admin"))) -> dict[str, Any]:
    uptime_seconds = (datetime.now(timezone.utc) - _SERVER_START_TIME).total_seconds()
    settings = AuthSettings.from_env()
    import os

    has_external_llm = bool(
        os.getenv("GROQ_API_KEY")
        or os.getenv("HUGGINGFACE_API_KEY")
        or os.getenv("HF_TOKEN")
    )
    return {
        "status": "ok",
        "uptime_seconds": round(uptime_seconds, 1),
        "started_at": _SERVER_START_TIME.isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "supported_transactions": ["837P", "837I", "835", "834"],
        "total_built_in_rules": get_total_rules_count(),
        "rule_count": get_total_rules_count(),
        "auth_enabled": settings.is_configured,
        "external_llm_enabled": has_external_llm,
        "limits": {
            "max_upload_mb": MAX_UPLOAD_SIZE // (1024 * 1024),
            "max_batch_mb": MAX_BATCH_SIZE // (1024 * 1024),
        },
        "engine_version": "1.0.0",
        "llm_providers": ["Groq/Llama-3.3", "HuggingFace", "Rule-based Fallback"],
    }


@app.get("/api/version")
def version(_identity: AuthIdentity = Depends(require_role("viewer"))) -> dict[str, Any]:
    return {
        "application": "EdiPro Healthcare EDI Gateway",
        "api_version": "1.0.0",
        "library": "validedi",
        "library_version": "0.4.0",
        "python_version": sys.version,
        "python_short": platform.python_version(),
        "platform": platform.system(),
        "supported_transactions": ["837P", "837I", "835", "834"],
        "hipaa_standard": "5010",
        "max_upload_mb": MAX_UPLOAD_SIZE // (1024 * 1024),
        "max_batch_mb": MAX_BATCH_SIZE // (1024 * 1024),
        "features": [
            "X12 EDI parsing",
            "HIPAA 5010 validation",
            "Batch processing",
            "835/837 reconciliation",
            "834 member delta",
            "Eligibility checking",
            "LLM-powered insights",
            "CSV/JSON/PDF export",
        ],
    }


@app.get("/api/stats/overview")
def get_system_stats(_identity: AuthIdentity = Depends(require_role("admin"))) -> dict[str, Any]:
    return {
        "status": "online",
        "supported_transactions": ["837P", "837I", "835", "834"],
        "active_rule_categories": [
            "Mandatory Segment Coverage",
            "NPI Luhn 10-Digit Verification",
            "ICD-10 / Diagnosis Code Formatting",
            "Balanced Claim Line Pricing",
            "HIPAA 5010 Segment Demarcation",
            "Cross-Segment & Date Consistency",
        ],
        "total_built_in_rules": get_total_rules_count(),
        "max_upload_mb": MAX_UPLOAD_SIZE // (1024 * 1024),
        "engine_version": "1.0.0",
    }


@app.get("/api/me")
def get_me(identity: AuthIdentity = Depends(require_role("viewer"))) -> dict[str, Any]:
    return {
        "subject": identity.subject,
        "role": identity.role,
        "auth_type": identity.auth_type,
    }


@app.post("/api/parse")
def parse_raw(
    request: ParseRequest,
    http_request: Request,
    _identity: AuthIdentity = Depends(require_role("viewer")),
) -> dict[str, Any]:
    parsed = parse_edi_content(request.content)
    http_request.state.transaction_type = parsed.transaction_type
    http_request.state.file_count = 1
    validation = validate_edi_content(parsed)
    tx_type = parsed.transaction_type or "UNKNOWN"
    outcome = "valid" if validation.valid else "invalid"
    VALIDATION_OUTCOMES.labels(transaction_type=tx_type, outcome=outcome).inc()
    return {
        "parse_result": parsed.model_dump(),
        "validation_result": validation.model_dump(),
    }


@app.post("/api/summary/837i")
def summarize_837i(
    request: ParseRequest,
    http_request: Request,
    _identity: AuthIdentity = Depends(require_role("viewer")),
) -> dict[str, Any]:
    """Return a structured 837I institutional claim summary from raw EDI content.

    Each entry in the response includes claim_id, total_billed, facility_type,
    statement_dates, and a list of SV2 revenue line items.
    """
    parsed = parse_edi_content(request.content)
    http_request.state.transaction_type = parsed.transaction_type
    http_request.state.file_count = 1
    if parsed.transaction_type not in {"837I", "UNKNOWN"}:
        raise HTTPException(
            status_code=422,
            detail=f"Expected 837I transaction; detected '{parsed.transaction_type}'.",
        )
    claims = build_837i_summary(parsed.segments)
    return {
        "transaction_type": parsed.transaction_type,
        "claim_count": len(claims),
        "total_billed": round(sum(float(c.get("total_billed", 0)) for c in claims), 2),
        "claims": claims,
    }


MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_BATCH_SIZE = 100 * 1024 * 1024  # 100 MB


@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(
    http_request: Request,
    file: UploadFile = File(...),
    _identity: AuthIdentity = Depends(require_role("operator")),
) -> UploadResponse:
    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds maximum limit of 50 MB.")

    UPLOAD_BYTES.inc(len(file_bytes))
    content = file_bytes.decode("utf-8", errors="ignore")
    parsed = parse_edi_content(content)
    http_request.state.transaction_type = parsed.transaction_type
    http_request.state.file_count = 1
    validation = validate_edi_content(parsed)
    tx_type = parsed.transaction_type or "UNKNOWN"
    outcome = "valid" if validation.valid else "invalid"
    VALIDATION_OUTCOMES.labels(transaction_type=tx_type, outcome=outcome).inc()

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
async def batch_upload(
    http_request: Request,
    file: UploadFile = File(...),
    _identity: AuthIdentity = Depends(require_role("operator")),
) -> BatchResult:
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Please upload a ZIP file for batch processing.")

    content = await file.read()
    if len(content) > MAX_BATCH_SIZE:
        raise HTTPException(status_code=413, detail="Batch ZIP file size exceeds maximum limit of 100 MB.")

    UPLOAD_BYTES.inc(len(content))
    zip_buffer = io.BytesIO(content)
    reports: list[ParsedFileReport] = []

    with zipfile.ZipFile(zip_buffer) as zf:
        for name in zf.namelist():
            safe_name = Path(name).name
            if not safe_name or not safe_name.lower().endswith((".edi", ".txt", ".dat", ".x12")):
                continue
            data = zf.read(name).decode("utf-8", errors="ignore")
            parsed = parse_edi_content(data)
            validation = validate_edi_content(parsed)
            r_tx_type = parsed.transaction_type or "UNKNOWN"
            r_outcome = "valid" if validation.valid else "invalid"
            VALIDATION_OUTCOMES.labels(transaction_type=r_tx_type, outcome=r_outcome).inc()
            reports.append(
                ParsedFileReport(filename=safe_name, parse_result=parsed, validation_result=validation)
            )

    failed = sum(1 for r in reports if not r.validation_result.valid)
    passed = len(reports) - failed

    http_request.state.transaction_type = "BATCH"
    http_request.state.file_count = len(reports)

    return BatchResult(total_files=len(reports), passed=passed, failed=failed, reports=reports)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    _identity: AuthIdentity = Depends(require_role("operator")),
) -> ChatResponse:
    answer = await ask_huggingface(request.question, request.context)
    return ChatResponse(answer=answer)


@app.post("/api/reconcile/835-837")
def reconcile_835_837(
    request: ReconcileRequest,
    http_request: Request,
    _identity: AuthIdentity = Depends(require_role("operator")),
) -> dict[str, Any]:
    http_request.state.transaction_type = "835/837"
    http_request.state.file_count = 2
    p837 = parse_edi_content(request.edi_837)
    p835 = parse_edi_content(request.edi_835)

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
def delta_834(
    request: DeltaRequest,
    http_request: Request,
    _identity: AuthIdentity = Depends(require_role("operator")),
) -> dict[str, Any]:
    http_request.state.transaction_type = "834"
    http_request.state.file_count = 2
    old_summary = build_834_summary(parse_edi_content(request.old_834).segments)
    new_summary = build_834_summary(parse_edi_content(request.new_834).segments)

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
def eligibility_check(
    request: EligibilityRequest,
    http_request: Request,
    _identity: AuthIdentity = Depends(require_role("operator")),
) -> dict[str, Any]:
    http_request.state.transaction_type = "834/837"
    http_request.state.file_count = 2
    members = build_834_summary(parse_edi_content(request.edi_834).segments)
    member_ids = {m.get("member_id") for m in members if m.get("member_id")}

    parsed_837 = parse_edi_content(request.edi_837)
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
def export_json(
    payload: dict[str, Any],
    http_request: Request,
    _identity: AuthIdentity = Depends(require_role("viewer")),
) -> StreamingResponse:
    http_request.state.file_count = 1
    return StreamingResponse(
        io.BytesIO(json_bytes(payload)),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=parsed.json"},
    )


@app.post("/api/export/errors-pdf")
def export_errors_pdf(
    payload: dict[str, Any],
    http_request: Request,
    _identity: AuthIdentity = Depends(require_role("viewer")),
) -> StreamingResponse:
    http_request.state.file_count = 1
    issues = payload.get("issues", [])
    return StreamingResponse(
        io.BytesIO(error_report_pdf_bytes(issues)),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=validation-report.pdf"},
    )


@app.post("/api/export/members-csv")
def export_members_csv(
    payload: dict[str, Any],
    http_request: Request,
    _identity: AuthIdentity = Depends(require_role("viewer")),
) -> StreamingResponse:
    http_request.state.file_count = 1
    rows = payload.get("rows", [])
    return StreamingResponse(
        io.BytesIO(csv_bytes(rows)),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=members.csv"},
    )


@app.post("/api/export/members-tsv")
def export_members_tsv(
    payload: dict[str, Any],
    http_request: Request,
    _identity: AuthIdentity = Depends(require_role("viewer")),
) -> StreamingResponse:
    """Tab-separated export — avoids comma issues in provider/member names."""
    http_request.state.file_count = 1
    rows = payload.get("rows", [])
    return StreamingResponse(
        io.BytesIO(tsv_bytes(rows)),
        media_type="text/tab-separated-values",
        headers={"Content-Disposition": "attachment; filename=members.tsv"},
    )


@app.post("/api/export/reconciliation-csv")
def export_reconciliation_csv(
    payload: dict[str, Any],
    http_request: Request,
    _identity: AuthIdentity = Depends(require_role("viewer")),
) -> StreamingResponse:
    http_request.state.file_count = 1
    rows = payload.get("rows", [])
    return StreamingResponse(
        io.BytesIO(csv_bytes(rows)),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reconciliation.csv"},
    )


@app.post("/api/export/corrected-edi")
def export_corrected_edi(
    payload: dict[str, Any],
    http_request: Request,
    _identity: AuthIdentity = Depends(require_role("viewer")),
) -> StreamingResponse:
    http_request.state.file_count = 1
    segments = payload.get("segments", [])
    try:
        text = to_segment_text([_segment_from_dict(s) for s in segments])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid segment payload: {exc}")

    return StreamingResponse(
        io.BytesIO(text.encode("utf-8")),
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=corrected.edi"},
    )


@app.post("/api/834/family-grouping")
def family_grouping(
    payload: dict[str, Any],
    http_request: Request,
    _identity: AuthIdentity = Depends(require_role("viewer")),
) -> dict[str, Any]:
    http_request.state.transaction_type = "834"
    http_request.state.file_count = 1
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

