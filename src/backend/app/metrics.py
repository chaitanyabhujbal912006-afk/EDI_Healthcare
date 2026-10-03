"""
Prometheus metrics module for EdiPro Healthcare EDI Gateway.
Provides:
- Metrics registry and definitions (counters, histograms)
- CIDR-based and role-based access control for /metrics
- Helper functions to increment metrics without leaking PHI or high-cardinality values
"""
from __future__ import annotations

import ipaddress
import os
from typing import Any

from fastapi import HTTPException, Request, Response, status
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

# 1. Request count by route template, method, and HTTP status
REQUEST_COUNT = Counter(
    "edipro_http_requests_total",
    "Total HTTP requests processed by EdiPro",
    ["route", "method", "status"],
)

# 2. Latency histogram by route template, method, and HTTP status
REQUEST_LATENCY = Histogram(
    "edipro_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["route", "method", "status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

# 3. Total uploaded payload bytes
UPLOAD_BYTES = Counter(
    "edipro_upload_bytes_total",
    "Total bytes uploaded across EDI upload endpoints",
)

# 4. Validation outcomes by transaction type and outcome
VALIDATION_OUTCOMES = Counter(
    "edipro_validation_outcomes_total",
    "Count of EDI validation outcomes by transaction type and outcome",
    ["transaction_type", "outcome"],
)

# 5. Rate limit rejections count
RATE_LIMIT_REJECTIONS = Counter(
    "edipro_rate_limit_rejections_total",
    "Total rate limit rejection occurrences",
)


def get_route_template(request: Request) -> str:
    """Extract the route template (e.g. /api/export/{fmt}) to prevent high cardinality."""
    route = request.scope.get("route")
    if route and hasattr(route, "path"):
        return str(route.path)
    path = request.url.path
    if path.startswith("/api/"):
        return path
    return "other"


def is_client_ip_allowed(client_ip: str, allowed_cidrs_env: str | None = None) -> bool:
    """Check if client_ip belongs to any CIDR in METRICS_ALLOWED_CIDRS."""
    raw = (
        allowed_cidrs_env
        if allowed_cidrs_env is not None
        else os.getenv("METRICS_ALLOWED_CIDRS", "")
    )
    if not raw.strip():
        return False
    try:
        ip = ipaddress.ip_address(client_ip.strip())
    except ValueError:
        return False

    for item in raw.split(","):
        cidr_str = item.strip()
        if not cidr_str:
            continue
        try:
            net = ipaddress.ip_network(cidr_str, strict=False)
            if ip in net:
                return True
        except ValueError:
            continue
    return False


def verify_metrics_access(request: Request) -> None:
    """
    Protect /metrics:
    Allow if client IP is within METRICS_ALLOWED_CIDRS,
    OR if user is authenticated with 'admin' role.
    Otherwise raise 403 Forbidden.
    """
    # Check client IP (or resolved proxy client IP)
    client_ip = getattr(request.state, "client_ip", None)
    if not client_ip and request.client:
        client_ip = request.client.host

    if client_ip and is_client_ip_allowed(client_ip):
        return

    # Check authenticated identity
    identity: Any = getattr(request.state, "auth_identity", None)
    if not identity:
        # Attempt resolution
        try:
            from app.config import AuthSettings
            from app.security import verify_api_key, verify_bearer_token

            settings = AuthSettings.from_env()
            auth_hdr = request.headers.get("authorization")
            if auth_hdr and auth_hdr.lower().startswith("bearer "):
                identity = verify_bearer_token(auth_hdr[7:].strip(), settings)
            elif "x-api-key" in request.headers:
                identity = verify_api_key(request.headers["x-api-key"].strip(), settings)
        except Exception:  # noqa: BLE001
            identity = None

    if identity and getattr(identity, "role", None) == "admin":
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access to /metrics requires admin role or an allowed network CIDR.",
    )


def metrics_endpoint(request: Request) -> Response:
    """FastAPI handler for GET /metrics."""
    verify_metrics_access(request)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
