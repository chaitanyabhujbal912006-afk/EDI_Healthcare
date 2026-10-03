"""
Unit tests for sliding window rate limiter:
- In-memory rate limiter backend
- Redis-backed rate limiter backend (using fakeredis)
- Keying logic (subject for authenticated, client IP for anonymous)
- Trusted proxy verification (X-Forwarded-For honored only from TRUSTED_PROXIES)
- Rejection raises HTTP 429 with Retry-After header and increments Prometheus counter
"""
from __future__ import annotations

import time

import fakeredis
import pytest
from app.metrics import RATE_LIMIT_REJECTIONS
from app.security import (
    AuthIdentity,
    InMemoryRateLimiter,
    RateLimiter,
    RedisRateLimiter,
    get_client_ip,
    is_trusted_proxy,
)
from fastapi import HTTPException, Request


def _mock_request(
    client_host: str = "192.168.1.100",
    headers: dict[str, str] | None = None,
    auth_identity: AuthIdentity | None = None,
) -> Request:
    scope = {
        "type": "http",
        "client": (client_host, 12345),
        "headers": [
            (k.lower().encode("latin1"), v.encode("latin1"))
            for k, v in (headers or {}).items()
        ],
    }
    req = Request(scope)
    if auth_identity:
        req.state.auth_identity = auth_identity
    return req


# ---------------------------------------------------------------------------
# 1. In-Memory Rate Limiter Backend Tests
# ---------------------------------------------------------------------------


def test_in_memory_rate_limiter_allows_and_rejects():
    limiter = InMemoryRateLimiter()
    key = "test-user-1"
    max_requests = 3
    window_seconds = 2

    # 3 allowed
    assert limiter.is_allowed(key, max_requests, window_seconds)[0] is True
    assert limiter.is_allowed(key, max_requests, window_seconds)[0] is True
    assert limiter.is_allowed(key, max_requests, window_seconds)[0] is True

    # 4th rejected
    allowed, retry_after = limiter.is_allowed(key, max_requests, window_seconds)
    assert allowed is False
    assert retry_after >= 1

    # Different key allowed
    assert limiter.is_allowed("other-user", max_requests, window_seconds)[0] is True


def test_in_memory_rate_limiter_window_slide():
    limiter = InMemoryRateLimiter()
    key = "test-slide"
    max_requests = 2
    window_seconds = 1  # 1 second window

    assert limiter.is_allowed(key, max_requests, window_seconds)[0] is True
    assert limiter.is_allowed(key, max_requests, window_seconds)[0] is True
    assert limiter.is_allowed(key, max_requests, window_seconds)[0] is False

    # Wait for window to expire
    time.sleep(1.1)
    assert limiter.is_allowed(key, max_requests, window_seconds)[0] is True


# ---------------------------------------------------------------------------
# 2. Redis Rate Limiter Backend Tests (fakeredis)
# ---------------------------------------------------------------------------


def test_redis_rate_limiter_allows_and_rejects():
    fake_redis = fakeredis.FakeRedis()
    limiter = RedisRateLimiter(fake_redis)
    key = "redis-user-1"
    max_requests = 3
    window_seconds = 5

    assert limiter.is_allowed(key, max_requests, window_seconds)[0] is True
    assert limiter.is_allowed(key, max_requests, window_seconds)[0] is True
    assert limiter.is_allowed(key, max_requests, window_seconds)[0] is True

    allowed, retry_after = limiter.is_allowed(key, max_requests, window_seconds)
    assert allowed is False
    assert retry_after >= 1

    # Distinct keys are isolated
    assert limiter.is_allowed("redis-user-2", max_requests, window_seconds)[0] is True


def test_redis_rate_limiter_window_slide():
    fake_redis = fakeredis.FakeRedis()
    limiter = RedisRateLimiter(fake_redis)
    key = "redis-slide"
    max_requests = 2
    window_seconds = 1

    assert limiter.is_allowed(key, max_requests, window_seconds)[0] is True
    assert limiter.is_allowed(key, max_requests, window_seconds)[0] is True
    assert limiter.is_allowed(key, max_requests, window_seconds)[0] is False

    time.sleep(1.1)
    assert limiter.is_allowed(key, max_requests, window_seconds)[0] is True


# ---------------------------------------------------------------------------
# 3. Trusted Proxy and IP Resolution Tests
# ---------------------------------------------------------------------------


def test_is_trusted_proxy():
    trusted = "10.0.0.0/8,172.16.0.1"
    assert is_trusted_proxy("10.1.2.3", trusted) is True
    assert is_trusted_proxy("172.16.0.1", trusted) is True
    assert is_trusted_proxy("192.168.1.1", trusted) is False
    assert is_trusted_proxy("invalid-ip", trusted) is False


def test_get_client_ip_trusted_proxy():
    req = _mock_request(
        client_host="10.0.0.5",
        headers={"X-Forwarded-For": "203.0.113.195, 10.0.0.5"},
    )
    # Direct IP is in trusted proxy network 10.0.0.0/8 -> honors X-Forwarded-For
    resolved_ip = get_client_ip(req, trusted_proxies_env="10.0.0.0/8")
    assert resolved_ip == "203.0.113.195"


def test_get_client_ip_untrusted_proxy_ignores_forwarded_for():
    req = _mock_request(
        client_host="198.51.100.2",
        headers={"X-Forwarded-For": "1.1.1.1"},
    )
    # Direct IP is NOT in trusted proxy list -> ignores spoofed X-Forwarded-For
    resolved_ip = get_client_ip(req, trusted_proxies_env="10.0.0.0/8")
    assert resolved_ip == "198.51.100.2"


# ---------------------------------------------------------------------------
# 4. RateLimiter Keying and HTTPException Tests
# ---------------------------------------------------------------------------


def test_rate_limiter_key_authenticated_subject():
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    identity = AuthIdentity(subject="doctor_who", role="operator", auth_type="api_key")
    req = _mock_request(client_host="192.168.1.50", auth_identity=identity)

    key = limiter.get_rate_limit_key(req)
    assert key == "sub:doctor_who"


def test_rate_limiter_key_anonymous_ip():
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    req = _mock_request(client_host="192.168.1.50")

    key = limiter.get_rate_limit_key(req)
    assert key == "ip:192.168.1.50"


def test_rate_limiter_raises_429_and_increments_counter():
    fake_redis = fakeredis.FakeRedis()
    limiter = RateLimiter(max_requests=2, window_seconds=60, redis_client=fake_redis)
    req = _mock_request(client_host="10.10.10.10")

    # First 2 allowed
    limiter.check(req)
    limiter.check(req)

    # 3rd request raises 429 with Retry-After header
    rejections_before = RATE_LIMIT_REJECTIONS._value.get()

    with pytest.raises(HTTPException) as exc_info:
        limiter.check(req)

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers
    assert int(exc_info.value.headers["Retry-After"]) >= 1

    rejections_after = RATE_LIMIT_REJECTIONS._value.get()
    assert rejections_after == rejections_before + 1
