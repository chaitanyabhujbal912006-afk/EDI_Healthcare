"""
Tests for OIDC JWT bearer authentication, role-based authorization,
API-key authentication, fail-closed production semantics, and structured audit logging.
"""
from __future__ import annotations

import io
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.main import app
from app.security import _get_jwk_client


@pytest.fixture(scope="module")
def rsa_keys():
    """Generate an RSA key pair for testing OIDC bearer tokens."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


class MockSigningKey:
    def __init__(self, key: Any):
        self.key = key


class MockJWKClient:
    def __init__(self, public_key: Any):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, _token: str) -> MockSigningKey:
        return MockSigningKey(self.public_key)


def _make_token(
    private_key: Any,
    sub: str = "test-user-001",
    roles: list[str] | None = None,
    issuer: str = "https://auth.edipro.health",
    audience: str = "edipro-api",
    expires_in_seconds: int = 300,
    algorithm: str = "RS256",
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": sub,
        "iss": issuer,
        "aud": audience,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()) - 10,
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    if roles is not None:
        payload["roles"] = roles
    if extra_claims:
        payload.update(extra_claims)

    headers = {"alg": algorithm, "typ": "JWT", "kid": "test-key-id"}
    return jwt.encode(payload, private_key, algorithm=algorithm, headers=headers)


# ---------------------------------------------------------------------------
# 1. Bearer Token Validation Tests
# ---------------------------------------------------------------------------


def test_valid_bearer_token(rsa_keys, monkeypatch):
    private_key, public_key = rsa_keys
    monkeypatch.setenv("OIDC_ISSUER", "https://auth.edipro.health")
    monkeypatch.setenv("OIDC_AUDIENCE", "edipro-api")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://auth.edipro.health/.well-known/jwks.json")

    token = _make_token(private_key, sub="alice@hospital.org", roles=["operator"])

    with patch("app.security._get_jwk_client", return_value=MockJWKClient(public_key)):
        client = TestClient(app)
        res = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["subject"] == "alice@hospital.org"
        assert data["role"] == "operator"
        assert data["auth_type"] == "bearer"


def test_expired_token(rsa_keys, monkeypatch):
    private_key, public_key = rsa_keys
    monkeypatch.setenv("OIDC_ISSUER", "https://auth.edipro.health")
    monkeypatch.setenv("OIDC_AUDIENCE", "edipro-api")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://auth.edipro.health/.well-known/jwks.json")

    # Expired 120 seconds ago (exceeds 60s clock skew)
    token = _make_token(private_key, expires_in_seconds=-120, roles=["admin"])

    with patch("app.security._get_jwk_client", return_value=MockJWKClient(public_key)):
        client = TestClient(app)
        res = client.get("/api/version", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401
        assert "expired" in res.json()["detail"].lower()


def test_wrong_audience(rsa_keys, monkeypatch):
    private_key, public_key = rsa_keys
    monkeypatch.setenv("OIDC_ISSUER", "https://auth.edipro.health")
    monkeypatch.setenv("OIDC_AUDIENCE", "edipro-api")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://auth.edipro.health/.well-known/jwks.json")

    token = _make_token(private_key, audience="wrong-client-aud", roles=["admin"])

    with patch("app.security._get_jwk_client", return_value=MockJWKClient(public_key)):
        client = TestClient(app)
        res = client.get("/api/version", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401
        assert "audience" in res.json()["detail"].lower()


def test_wrong_issuer(rsa_keys, monkeypatch):
    private_key, public_key = rsa_keys
    monkeypatch.setenv("OIDC_ISSUER", "https://auth.edipro.health")
    monkeypatch.setenv("OIDC_AUDIENCE", "edipro-api")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://auth.edipro.health/.well-known/jwks.json")

    token = _make_token(private_key, issuer="https://untrusted-idp.com", roles=["admin"])

    with patch("app.security._get_jwk_client", return_value=MockJWKClient(public_key)):
        client = TestClient(app)
        res = client.get("/api/version", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401
        assert "issuer" in res.json()["detail"].lower()


def test_tampered_signature(rsa_keys, monkeypatch):
    private_key, public_key = rsa_keys
    monkeypatch.setenv("OIDC_ISSUER", "https://auth.edipro.health")
    monkeypatch.setenv("OIDC_AUDIENCE", "edipro-api")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://auth.edipro.health/.well-known/jwks.json")

    token = _make_token(private_key, roles=["admin"])
    # Tamper with signature by changing last characters
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")

    with patch("app.security._get_jwk_client", return_value=MockJWKClient(public_key)):
        client = TestClient(app)
        res = client.get("/api/version", headers={"Authorization": f"Bearer {tampered}"})
        assert res.status_code == 401
        assert "signature" in res.json()["detail"].lower()


def test_alg_none_rejected(monkeypatch):
    monkeypatch.setenv("OIDC_ISSUER", "https://auth.edipro.health")
    monkeypatch.setenv("OIDC_AUDIENCE", "edipro-api")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://auth.edipro.health/.well-known/jwks.json")

    # Insecure alg=none token
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "sub": "attacker",
        "iss": "https://auth.edipro.health",
        "aud": "edipro-api",
        "roles": ["admin"],
        "exp": int(datetime.now(timezone.utc).timestamp()) + 300,
    }
    raw_token = f"{jwt.utils.base64url_encode(json.dumps(header).encode()).decode()}.{jwt.utils.base64url_encode(json.dumps(payload).encode()).decode()}."

    client = TestClient(app)
    res = client.get("/api/version", headers={"Authorization": f"Bearer {raw_token}"})
    assert res.status_code == 401
    assert "none" in res.json()["detail"].lower()


def test_symmetric_hs_rejected(monkeypatch):
    monkeypatch.setenv("OIDC_ISSUER", "https://auth.edipro.health")
    monkeypatch.setenv("OIDC_AUDIENCE", "edipro-api")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://auth.edipro.health/.well-known/jwks.json")

    # Token signed symmetrically with HS256
    hs_token = jwt.encode(
        {
            "sub": "attacker",
            "iss": "https://auth.edipro.health",
            "aud": "edipro-api",
            "roles": ["admin"],
            "exp": int(datetime.now(timezone.utc).timestamp()) + 300,
        },
        "symmetric-secret-key-32-bytes-minimum!",
        algorithm="HS256",
    )

    client = TestClient(app)
    res = client.get("/api/version", headers={"Authorization": f"Bearer {hs_token}"})
    assert res.status_code == 401
    assert "symmetric" in res.json()["detail"].lower() or "rejected" in res.json()["detail"].lower()


def test_missing_role_claim(rsa_keys, monkeypatch):
    private_key, public_key = rsa_keys
    monkeypatch.setenv("OIDC_ISSUER", "https://auth.edipro.health")
    monkeypatch.setenv("OIDC_AUDIENCE", "edipro-api")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://auth.edipro.health/.well-known/jwks.json")

    # Token without roles
    token = _make_token(private_key, sub="bob", roles=None)

    with patch("app.security._get_jwk_client", return_value=MockJWKClient(public_key)):
        client = TestClient(app)
        res = client.get("/api/version", headers={"Authorization": f"Bearer {token}"})
        # Missing role cannot satisfy require_role("viewer") -> 403 Forbidden
        assert res.status_code == 403
        assert "Forbidden" in res.json()["detail"]


# ---------------------------------------------------------------------------
# 2. Role-Based Access Control and API Key Semantics
# ---------------------------------------------------------------------------


def test_api_keys_roles_and_hierarchy(monkeypatch):
    monkeypatch.setenv(
        "EDI_API_KEYS",
        "viewer-key-1:viewer,operator-key-1:operator,admin-key-1:admin,default-role-key",
    )

    client = TestClient(app)

    # 1. Viewer key:
    # Allowed on viewer endpoints (/api/version, /api/me)
    res = client.get("/api/version", headers={"X-API-Key": "viewer-key-1"})
    assert res.status_code == 200

    me_res = client.get("/api/me", headers={"X-API-Key": "viewer-key-1"})
    assert me_res.status_code == 200
    assert me_res.json()["role"] == "viewer"
    assert me_res.json()["auth_type"] == "api_key"

    # Denied (403) on operator endpoint (/api/upload)
    up_res = client.post(
        "/api/upload",
        headers={"X-API-Key": "viewer-key-1"},
        files={"file": ("test.edi", b"ISA*00*...~", "text/plain")},
    )
    assert up_res.status_code == 403

    # Denied (403) on admin endpoint (/api/health/detailed)
    admin_res = client.get("/api/health/detailed", headers={"X-API-Key": "viewer-key-1"})
    assert admin_res.status_code == 403

    # 2. Operator key:
    # Allowed on viewer and operator endpoints
    assert client.get("/api/version", headers={"X-API-Key": "operator-key-1"}).status_code == 200
    # Denied (403) on admin endpoint
    assert client.get("/api/health/detailed", headers={"X-API-Key": "operator-key-1"}).status_code == 403

    # 3. Default role key (unspecified role defaults to operator):
    me_default = client.get("/api/me", headers={"X-API-Key": "default-role-key"}).json()
    assert me_default["role"] == "operator"

    # 4. Admin key:
    # Allowed on everything including admin endpoints
    assert client.get("/api/health/detailed", headers={"X-API-Key": "admin-key-1"}).status_code == 200
    assert client.get("/api/stats/overview", headers={"X-API-Key": "admin-key-1"}).status_code == 200


def test_401_vs_403_semantics(monkeypatch):
    monkeypatch.setenv("EDI_API_KEYS", "low-priv-key:viewer")

    client = TestClient(app)

    # Missing credentials when auth is configured -> 401 Unauthorized
    res_no_auth = client.get("/api/version")
    assert res_no_auth.status_code == 401
    assert "Missing authentication" in res_no_auth.json()["detail"]

    # Invalid API key -> 401 Unauthorized
    res_bad_key = client.get("/api/version", headers={"X-API-Key": "nonexistent-bad-key"})
    assert res_bad_key.status_code == 401
    assert "Invalid API key" in res_bad_key.json()["detail"]

    # Valid key with insufficient role -> 403 Forbidden
    res_forbidden = client.get("/api/health/detailed", headers={"X-API-Key": "low-priv-key"})
    assert res_forbidden.status_code == 403
    assert "Forbidden" in res_forbidden.json()["detail"]


# ---------------------------------------------------------------------------
# 3. Fail-Closed Production Behavior
# ---------------------------------------------------------------------------


def test_production_fails_closed_when_unconfigured(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("OIDC_ISSUER", raising=False)
    monkeypatch.delenv("OIDC_JWKS_URL", raising=False)
    monkeypatch.delenv("EDI_API_KEYS", raising=False)
    monkeypatch.delenv("EDI_API_KEY", raising=False)

    client = TestClient(app)
    # /api/health remains accessible for container liveness probes
    assert client.get("/api/health").status_code == 200

    # Protected endpoints fail closed with 503 Service Unavailable
    res = client.get("/api/version")
    assert res.status_code == 503
    assert "fail-closed" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. Audit Logging and PHI Leakage Prevention Tests
# ---------------------------------------------------------------------------


def test_audit_log_allowed_and_denied(monkeypatch, caplog):
    monkeypatch.setenv("EDI_API_KEYS", "test-key-op:operator")
    caplog.set_level(logging.INFO, logger="edipro.audit")

    client = TestClient(app)

    # 1. Allowed request
    res_ok = client.get(
        "/api/version",
        headers={"X-API-Key": "test-key-op", "X-Request-ID": "req-allowed-123"},
    )
    assert res_ok.status_code == 200
    assert res_ok.headers.get("X-Request-ID") == "req-allowed-123"

    # Find audit log record for req-allowed-123
    audit_records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "edipro.audit" and "req-allowed-123" in record.message
    ]
    assert len(audit_records) == 1
    rec = audit_records[0]
    assert rec["request_id"] == "req-allowed-123"
    assert rec["outcome"] == "allowed"
    assert rec["status"] == 200
    assert rec["role"] == "operator"
    assert rec["method"] == "GET"
    assert rec["path"] == "/api/version"
    assert isinstance(rec["duration_ms"], (int, float))

    # 2. Denied request (invalid key)
    res_denied = client.get(
        "/api/version",
        headers={"X-API-Key": "wrong-key-xyz", "X-Request-ID": "req-denied-456"},
    )
    assert res_denied.status_code == 401

    denied_records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "edipro.audit" and "req-denied-456" in record.message
    ]
    assert len(denied_records) == 1
    d_rec = denied_records[0]
    assert d_rec["request_id"] == "req-denied-456"
    assert d_rec["outcome"] == "denied"
    assert d_rec["status"] == 401
    assert d_rec["role"] == "none"

    # 3. /api/health is skipped from audit logging
    caplog.clear()
    client.get("/api/health")
    health_records = [r for r in caplog.records if r.name == "edipro.audit"]
    assert len(health_records) == 0


def test_audit_log_zero_phi_leakage(monkeypatch, caplog):
    """
    HIPAA PHI Safety Verification:
    Parse and upload synthetic EDI files with synthetic patient and provider names.
    Ensure that no patient names, identifiers, or EDI body contents leak into the audit log.
    """
    monkeypatch.setenv("EDI_API_KEYS", "pipeline-key:operator")
    caplog.set_level(logging.INFO, logger="edipro.audit")

    client = TestClient(app)

    # Read synthetic sample files
    sample_837p_path = Path(__file__).resolve().parents[1] / "sample_837p.edi"
    assert sample_837p_path.exists(), "sample_837p.edi must exist"
    edi_content = sample_837p_path.read_text(encoding="utf-8")

    # Known synthetic patient & provider identifiers in sample_837p.edi
    synthetic_sensitive_terms = [
        "DOE",
        "JOHN",
        "SMITH",
        "JANE",
        "ABC123456789",  # Member ID
        "456 OAK AVE",   # Address
        "SOMEWHERE",
        "19800101",      # DOB
        "GENERAL HOSPITAL",
        "ACME BILLING",
        "5551234567",    # Phone
    ]

    # Perform API upload request
    res = client.post(
        "/api/upload",
        headers={"X-API-Key": "pipeline-key", "X-Request-ID": "audit-phi-test-001"},
        files={"file": ("sample_837p.edi", edi_content.encode("utf-8"), "application/octet-stream")},
    )
    assert res.status_code == 200

    # Perform API parse request
    res_parse = client.post(
        "/api/parse",
        headers={"X-API-Key": "pipeline-key", "X-Request-ID": "audit-phi-test-002"},
        json={"content": edi_content},
    )
    assert res_parse.status_code == 200

    # Collect all captured audit log lines
    audit_messages = [
        record.message for record in caplog.records if record.name == "edipro.audit"
    ]
    assert len(audit_messages) >= 2, "Expected at least 2 audit log records"

    full_audit_stream = "\n".join(audit_messages)

    # Verify each audit record is valid JSON and contains required structured fields
    for msg in audit_messages:
        entry = json.loads(msg)
        assert "timestamp" in entry
        assert "request_id" in entry
        assert "subject" in entry
        assert "role" in entry
        assert "method" in entry
        assert "path" in entry
        assert "status" in entry
        assert "duration_ms" in entry
        assert "bytes_in" in entry
        assert "file_count" in entry
        assert "transaction_type" in entry
        assert "outcome" in entry
        # Filename and payload must NEVER appear in the audit record
        assert "sample_837p.edi" not in msg
        assert "content" not in entry
        assert "body" not in entry

    # Verify zero synthetic PHI leaked into audit log stream
    for term in synthetic_sensitive_terms:
        assert term not in full_audit_stream, (
            f"PHI LEAK DETECTED in audit log: '{term}' was found in the audit stream!"
        )
