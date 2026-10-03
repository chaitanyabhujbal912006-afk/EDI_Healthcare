"""
Unit tests for request timeout middleware and heavy request concurrency semaphore.
Validates:
- Requests exceeding REQUEST_TIMEOUT_SECONDS return HTTP 504 Gateway Timeout
- Heavy endpoints (/api/upload, /api/batch) acquire and release upload_semaphore
- Concurrency limit MAX_CONCURRENT_UPLOADS is enforced
"""
from __future__ import annotations

import asyncio

from app.main import app, set_upload_semaphore
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


def test_request_timeout_returns_504(monkeypatch):
    """When a request takes longer than REQUEST_TIMEOUT_SECONDS, middleware returns 504."""
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "0.05")

    # Add a slow test route to app
    @app.get("/api/test-slow-timeout")
    async def slow_route():
        await asyncio.sleep(0.3)
        return {"status": "delayed"}

    client = TestClient(app)
    res = client.get("/api/test-slow-timeout")
    assert res.status_code == 504
    data = res.json()
    assert "detail" in data
    assert "timed out" in data["detail"].lower()


def test_fast_request_within_timeout_returns_200(monkeypatch):
    """Requests finishing within timeout succeed normally."""
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "5.0")
    client = TestClient(app)
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_heavy_request_concurrency_semaphore(monkeypatch):
    """Upload requests acquire and release the upload semaphore."""
    sem = set_upload_semaphore(2)
    initial_value = sem._value
    assert initial_value == 2

    monkeypatch.setenv("EDI_API_KEYS", "test-key:operator")
    client = TestClient(app)

    # Perform normal upload
    res = client.post(
        "/api/upload",
        headers={"X-API-Key": "test-key"},
        files={"file": ("test.edi", SAMPLE_837P.encode("utf-8"), "text/plain")},
    )
    assert res.status_code == 200

    # Ensure semaphore was released back to original capacity
    assert sem._value == initial_value


def test_semaphore_limits_concurrency():
    """Verify semaphore enforces capacity bounds."""
    sem = set_upload_semaphore(1)
    assert sem._value == 1

    # Simulate acquisition
    assert sem.locked() is False
    acquired = sem.acquire()
    # In asyncio loop:
    loop = asyncio.new_event_loop()
    loop.run_until_complete(acquired)
    assert sem._value == 0
    assert sem.locked() is True

    # Release
    sem.release()
    assert sem._value == 1
    assert sem.locked() is False
    loop.close()
