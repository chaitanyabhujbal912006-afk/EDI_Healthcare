"""
Tests for Prometheus metrics at /metrics:
- Route template and status labels
- Upload bytes tracking
- Validation outcome counts by transaction_type
- Access protection via METRICS_ALLOWED_CIDRS or admin role
- Verification that filename and subject are never labeled
"""
from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

SAMPLE_837P = (
    "ISA*00*          *00*          *ZZ*SUBMITTER1     *ZZ*RECEIVER1      *260824*1030*U*00501*000000001*0*P*>~\n"
    "GS*HC*SUBMITTER1*RECEIVER1*20260824*1030*1*X*005010X222A1~\n"
    "ST*837*0001*005010X222A1~\n"
    "BHT*0019*00*244579*20260824*1030*CH~\n"
    "NM1*41*2*PREMIUM HEALTH INC*****46*1234567890~\n"
    "PER*IC*EDI DEPT*TE*8005551212~\n"
    "NM1*40*2*HEALTHPAY INC*****46*9876543210~\n"
    "HL*1**20*1~\n"
    "PRV*BI*PXC*207Q00000X~\n"
    "NM1*85*2*METRO MEDICAL CENTER*****XX*1992837465~\n"
    "N3*100 MAIN STREET~\n"
    "N4*METROPOLIS*NY*10001~\n"
    "REF*EI*123456789~\n"
    "HL*2*1*22*0~\n"
    "SBR*P*18*GRP12345******CI~\n"
    "NM1*IL*1*SMITH*JOHN*M***MI*SUB12345678~\n"
    "N3*456 ELM AVE~\n"
    "N4*METROPOLIS*NY*10001~\n"
    "DMG*D8*19800512*M~\n"
    "NM1*PR*2*HEALTHPAY INC*****PI*98765~\n"
    "CLM*CLM-99401*1250.00***11:B:1*Y*A*Y*Y~\n"
    "HI*BK:99214*BF:78009~\n"
    "LX*1~\n"
    "SV1*HC:99214*1250.00*UN*1***1~\n"
    "DTP*472*D8*20260820~\n"
    "SE*25*0001~\n"
    "GE*1*1~\n"
    "IEA*1*000000001~"
)


def test_metrics_protected_by_default(monkeypatch):
    """Access to /metrics without admin role or CIDR match must return 403."""
    monkeypatch.delenv("METRICS_ALLOWED_CIDRS", raising=False)
    monkeypatch.setenv("EDI_API_KEYS", "user-key:operator,admin-key:admin")
    client = TestClient(app)

    # 1. Unauthenticated request without CIDR match
    res_anon = client.get("/metrics")
    assert res_anon.status_code == 403

    # 2. Operator role request
    res_operator = client.get("/metrics", headers={"X-API-Key": "user-key"})
    assert res_operator.status_code == 403


def test_metrics_allowed_via_admin_role(monkeypatch):
    """Admin role should be granted access to /metrics."""
    monkeypatch.delenv("METRICS_ALLOWED_CIDRS", raising=False)
    monkeypatch.setenv("EDI_API_KEYS", "admin-key:admin")
    client = TestClient(app)

    res = client.get("/metrics", headers={"X-API-Key": "admin-key"})
    assert res.status_code == 200
    assert "edipro_http_requests_total" in res.text


def test_metrics_allowed_via_cidr(monkeypatch):
    """Clients within allowed CIDR range can access /metrics without auth."""
    # TestClient connects as client IP (or we mock client host)
    monkeypatch.setenv("METRICS_ALLOWED_CIDRS", "10.0.0.0/8,192.168.1.0/24")
    client = TestClient(app, client=("192.168.1.42", 54321))

    res = client.get("/metrics")
    assert res.status_code == 200
    assert "edipro_http_requests_total" in res.text


def test_metrics_series_populated_after_requests(monkeypatch):
    """Make sample API requests and verify all Prometheus metrics series are populated."""
    monkeypatch.setenv("METRICS_ALLOWED_CIDRS", "10.0.0.0/8,127.0.0.1/32,testclient")
    monkeypatch.setenv("EDI_API_KEYS", "test-admin:admin")
    client = TestClient(app, client=("10.0.1.1", 50000))

    # 1. Request to /api/health
    res_health = client.get("/api/health")
    assert res_health.status_code == 200

    # 2. Request to /api/parse
    res_parse = client.post(
        "/api/parse",
        headers={"X-API-Key": "test-admin"},
        json={"content": SAMPLE_837P},
    )
    assert res_parse.status_code == 200

    # 3. Request to /api/upload
    res_upload = client.post(
        "/api/upload",
        headers={"X-API-Key": "test-admin"},
        files={"file": ("synthetic_claim_file.edi", SAMPLE_837P.encode("utf-8"), "text/plain")},
    )
    assert res_upload.status_code == 200

    # 4. Fetch metrics
    metrics_res = client.get("/metrics", headers={"X-API-Key": "test-admin"})
    assert metrics_res.status_code == 200
    text = metrics_res.text

    # Verify series exist
    assert "edipro_http_requests_total" in text
    assert 'route="/api/health"' in text
    assert 'route="/api/parse"' in text
    assert 'route="/api/upload"' in text
    assert "edipro_http_request_duration_seconds" in text
    assert "edipro_upload_bytes_total" in text
    assert "edipro_validation_outcomes_total" in text
    assert 'transaction_type="837P"' in text

    # Verify filenames and subjects are NEVER labeled
    assert "synthetic_claim_file.edi" not in text
    assert "test-admin" not in text
    assert "SMITH" not in text
