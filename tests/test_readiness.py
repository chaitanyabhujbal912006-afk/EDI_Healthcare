"""
Tests for readiness probe (/api/ready) and liveness probe (/api/health):
- /api/health acts as lightweight liveness probe (200 OK)
- /api/ready verifies that validation configurations (837p, 837i, 835, 834) load
- /api/ready returns 503 if validation configs fail to load
- /api/ready returns 503 during graceful shutdown
"""
from __future__ import annotations

from unittest.mock import patch

import app.main as app_main
import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_shutdown_flag():
    app_main._is_shutting_down = False
    yield
    app_main._is_shutting_down = False


def test_liveness_endpoint():
    """Verify /api/health acts as liveness probe."""
    client = TestClient(app)
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_readiness_endpoint_success():
    """Verify /api/ready verifies that the validation config loads."""
    client = TestClient(app)
    res = client.get("/api/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["ready"] is True
    assert data["validation_config"] == "loaded"
    assert "837p" in data["transactions"]
    assert "837i" in data["transactions"]
    assert "835" in data["transactions"]
    assert "834" in data["transactions"]


def test_readiness_endpoint_failure_when_config_fails():
    """If validation config fails to load, /api/ready returns 503 Service Unavailable."""
    client = TestClient(app)
    with patch("validedi.engine.config_loader.ConfigLoader.get_config", side_effect=RuntimeError("Corrupt YAML")):
        res = client.get("/api/ready")
        assert res.status_code == 503
        data = res.json()
        assert "not_ready" in str(data)


def test_readiness_endpoint_during_shutdown():
    """During shutdown, /api/ready signals 503 while /api/health still responds for liveness."""
    client = TestClient(app)
    original_state = app_main._is_shutting_down
    try:
        app_main._is_shutting_down = True
        res_ready = client.get("/api/ready")
        assert res_ready.status_code == 503
        assert "shutting_down" in str(res_ready.json())

        # Liveness remains responsive
        res_health = client.get("/api/health")
        assert res_health.status_code == 200
    finally:
        app_main._is_shutting_down = original_state
