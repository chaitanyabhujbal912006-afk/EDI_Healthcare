"""
Authentication and Authorization module for EdiPro Healthcare EDI Gateway.

Supports:
- OIDC/JWT Bearer tokens (RS/ES algorithms, JWKS caching, 60s clock skew)
- API Keys via X-API-Key with constant-time comparison and role mapping
- Role-based access control (viewer, operator, admin)
- Fail-closed security in production (503 if unconfigured)
"""
from __future__ import annotations

import hashlib
import ipaddress
import logging
import os
import secrets
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import jwt
from fastapi import Header, HTTPException, Request, status

try:
    import redis
except ImportError:
    redis = None  # type: ignore

from app.config import AuthSettings
from app.metrics import RATE_LIMIT_REJECTIONS

logger = logging.getLogger("edipro.security")

# Role hierarchy: higher integer includes lower capabilities
ROLE_HIERARCHY: dict[str, int] = {
    "viewer": 1,
    "operator": 2,
    "admin": 3,
}

_jwk_clients: dict[str, jwt.PyJWKClient] = {}


@dataclass
class AuthIdentity:
    subject: str
    role: str
    auth_type: str  # "bearer" | "api_key" | "dev"
    claims: dict[str, Any] = field(default_factory=dict)


def _get_jwk_client(jwks_url: str) -> jwt.PyJWKClient:
    """Return a cached PyJWKClient instance."""
    if jwks_url not in _jwk_clients:
        _jwk_clients[jwks_url] = jwt.PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=300)
    return _jwk_clients[jwks_url]


def _extract_highest_role(role_val: Any) -> str:
    """Extract highest valid role from role claim value."""
    if not role_val:
        return ""
    candidates: list[str] = []
    if isinstance(role_val, list):
        candidates = [str(r).strip().lower() for r in role_val]
    elif isinstance(role_val, str):
        candidates = [r.strip().lower() for r in role_val.split(",")]
    else:
        candidates = [str(role_val).strip().lower()]

    highest_role = ""
    highest_weight = 0
    for r in candidates:
        weight = ROLE_HIERARCHY.get(r, 0)
        if weight > highest_weight:
            highest_weight = weight
            highest_role = r
    return highest_role


def verify_bearer_token(token: str, settings: AuthSettings) -> AuthIdentity:
    """Validate JWT token against OIDC settings with clock skew and algorithm checks."""
    try:
        unverified_header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Malformed token header: {exc}",
        ) from exc

    alg = unverified_header.get("alg", "")
    if not alg or alg.lower() == "none":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Algorithm 'none' is not allowed.",
        )
    if alg.startswith("HS"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Symmetric algorithm '{alg}' is rejected when asymmetric JWKS is required.",
        )

    allowed_algs = ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512"]
    if alg not in allowed_algs:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unsupported algorithm '{alg}'.",
        )

    if not settings.oidc_jwks_url:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC JWKS URL is not configured.",
        )

    try:
        jwk_client = _get_jwk_client(settings.oidc_jwks_url)
        signing_key = jwk_client.get_signing_key_from_jwt(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unable to find signing key in JWKS: {exc}",
        ) from exc

    try:
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=allowed_algs,
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            leeway=60,  # 60s clock skew tolerance
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": bool(settings.oidc_audience),
                "verify_iss": bool(settings.oidc_issuer),
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        ) from exc
    except jwt.InvalidAudienceError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token audience.",
        ) from exc
    except jwt.InvalidIssuerError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer.",
        ) from exc
    except jwt.ImmatureSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not yet valid (nbf).",
        ) from exc
    except jwt.InvalidSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {exc}",
        ) from exc

    sub = str(payload.get("sub", ""))
    role_val = payload.get(settings.role_claim)
    role = _extract_highest_role(role_val)

    return AuthIdentity(
        subject=sub or "anonymous",
        role=role,
        auth_type="bearer",
        claims=payload,
    )


def verify_api_key(api_key: str, settings: AuthSettings) -> AuthIdentity | None:
    """Verify an API key using constant-time comparison and return identity if valid."""
    if not api_key:
        return None

    for configured_key, configured_role in settings.api_keys.items():
        if secrets.compare_digest(api_key, configured_key):
            fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:8]
            return AuthIdentity(
                subject=fingerprint,
                role=configured_role,
                auth_type="api_key",
                claims={"role": configured_role},
            )
    return None


async def get_current_identity(
    request: Request,
    authorization: str | None = Header(None, alias="Authorization"),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> AuthIdentity:
    """FastAPI dependency to resolve and authenticate the request identity."""
    settings = AuthSettings.from_env()

    # Fail closed in production if no auth is configured
    if settings.is_production and not settings.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication not configured in production. Server is in fail-closed mode.",
        )

    # 1. Check Bearer token
    bearer_identity: AuthIdentity | None = None
    bearer_error: HTTPException | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        try:
            bearer_identity = verify_bearer_token(token, settings)
        except HTTPException as exc:
            bearer_error = exc

    # 2. Check X-API-Key
    api_key_identity: AuthIdentity | None = None
    if x_api_key:
        api_key_identity = verify_api_key(x_api_key.strip(), settings)

    # Authorized if either is valid
    if bearer_identity:
        request.state.auth_identity = bearer_identity
        return bearer_identity
    if api_key_identity:
        request.state.auth_identity = api_key_identity
        return api_key_identity

    # If an invalid bearer token was sent, raise that 401 error
    if bearer_error:
        raise bearer_error

    # If an invalid X-API-Key was sent, raise 401
    if x_api_key and not api_key_identity:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    # If auth is configured but no credentials were provided
    if settings.is_configured:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials. Provide Authorization: Bearer or X-API-Key.",
        )

    # If unconfigured in non-production, allow developer access with admin role
    dev_identity = AuthIdentity(subject="dev-user", role="admin", auth_type="dev")
    request.state.auth_identity = dev_identity
    return dev_identity


def require_role(min_role: str) -> Callable:
    """Dependency factory checking that the authenticated user possesses at least min_role."""
    min_weight = ROLE_HIERARCHY.get(min_role.lower(), 0)

    async def role_dependency(
        request: Request,
        authorization: str | None = Header(None, alias="Authorization"),
        x_api_key: str | None = Header(None, alias="X-API-Key"),
    ) -> AuthIdentity:
        identity = await get_current_identity(
            request=request, authorization=authorization, x_api_key=x_api_key
        )
        user_weight = ROLE_HIERARCHY.get(identity.role.lower(), 0)

        if not identity.role or user_weight < min_weight:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: role '{min_role}' required, but user has '{identity.role or 'none'}'.",
            )
        return identity

    return role_dependency


def authenticate_request(
    request: Request, settings: AuthSettings | None = None
) -> AuthIdentity | None:
    """Resolve and verify identity from request state, Authorization header, or X-API-Key."""
    identity: AuthIdentity | None = getattr(request.state, "auth_identity", None)
    if identity:
        return identity

    if settings is None:
        settings = AuthSettings.from_env()

    auth_hdr = request.headers.get("authorization", "")
    if auth_hdr.lower().startswith("bearer "):
        token = auth_hdr[7:].strip()
        try:
            identity = verify_bearer_token(token, settings)
            request.state.auth_identity = identity
            return identity
        except Exception:  # noqa: BLE001
            return None

    api_key = request.headers.get("x-api-key", "")
    if api_key:
        identity = verify_api_key(api_key.strip(), settings)
        if identity:
            request.state.auth_identity = identity
            return identity

    return None


def is_trusted_proxy(ip_str: str, trusted_proxies_env: str | None = None) -> bool:
    """Check if given IP matches any address or CIDR network in TRUSTED_PROXIES."""
    raw = (
        trusted_proxies_env
        if trusted_proxies_env is not None
        else os.getenv("TRUSTED_PROXIES", "")
    )
    if not raw.strip() or not ip_str.strip():
        return False
    try:
        ip = ipaddress.ip_address(ip_str.strip())
    except ValueError:
        return False

    for item in raw.split(","):
        cidr = item.strip()
        if not cidr:
            continue
        try:
            net = ipaddress.ip_network(cidr, strict=False)
            if ip in net:
                return True
        except ValueError:
            continue
    return False


def get_client_ip(request: Request, trusted_proxies_env: str | None = None) -> str:
    """
    Resolve client IP:
    If direct connection IP is in TRUSTED_PROXIES, use first IP in X-Forwarded-For;
    otherwise use direct client host (preventing X-Forwarded-For spoofing).
    """
    direct_ip = request.client.host if request.client else "127.0.0.1"
    if is_trusted_proxy(direct_ip, trusted_proxies_env):
        xff = request.headers.get("x-forwarded-for")
        if xff:
            first_ip = xff.split(",")[0].strip()
            if first_ip:
                return first_ip
    return direct_ip


class BaseRateLimiter(ABC):
    """Abstract sliding window rate limiter backend."""

    @abstractmethod
    def is_allowed(
        self, key: str, max_requests: int, window_seconds: int
    ) -> tuple[bool, int]:
        """Return (allowed: bool, retry_after: int)."""

    @abstractmethod
    def reset(self) -> None:
        """Reset rate limiter state."""


class InMemoryRateLimiter(BaseRateLimiter):
    """Thread-safe in-memory sliding window rate limiter."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: dict[str, list[float]] = {}

    def is_allowed(
        self, key: str, max_requests: int, window_seconds: int
    ) -> tuple[bool, int]:
        now = time.time()
        window_start = now - window_seconds
        with self._lock:
            timestamps = self._history.get(key, [])
            valid_timestamps = [t for t in timestamps if t > window_start]
            if len(valid_timestamps) >= max_requests:
                oldest = valid_timestamps[0]
                retry_after = max(1, int(window_seconds - (now - oldest)) + 1)
                self._history[key] = valid_timestamps
                return False, retry_after

            valid_timestamps.append(now)
            self._history[key] = valid_timestamps
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._history.clear()


class RedisRateLimiter(BaseRateLimiter):
    """Redis-backed sliding window rate limiter using sorted sets."""

    def __init__(self, redis_client: Any) -> None:
        self.client = redis_client

    def is_allowed(
        self, key: str, max_requests: int, window_seconds: int
    ) -> tuple[bool, int]:
        redis_key = f"ratelimit:{key}"
        now = time.time()
        clear_before = now - window_seconds

        pipe = self.client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, clear_before)
        pipe.zcard(redis_key)
        pipe.zrange(redis_key, 0, 0, withscores=True)
        results = pipe.execute()

        current_count = results[1]
        if current_count < max_requests:
            p2 = self.client.pipeline()
            member = f"{now}:{uuid.uuid4().hex[:6]}"
            p2.zadd(redis_key, {member: now})
            p2.expire(redis_key, int(window_seconds) + 1)
            p2.execute()
            return True, 0
        else:
            oldest_score = results[2][0][1] if results[2] else now
            retry_after = max(1, int(window_seconds - (now - oldest_score)) + 1)
            return False, retry_after

    def reset(self) -> None:
        try:
            keys = self.client.keys("ratelimit:*")
            if keys:
                self.client.delete(*keys)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Redis rate limit reset error: %s", exc)


class RateLimiter:
    """
    Sliding window rate limiter supporting both in-memory and Redis backends.
    - Keyed by subject if authenticated else client IP
    - Honors X-Forwarded-For only from trusted proxies (TRUSTED_PROXIES)
    - Defaults to in-memory; uses Redis when REDIS_URL or redis_client is provided
    - Increments RATE_LIMIT_REJECTIONS and raises HTTP 429 on limit breach
    """

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60,
        redis_url: str | None = None,
        redis_client: Any | None = None,
        trusted_proxies: str | None = None,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.trusted_proxies = trusted_proxies

        if redis_client is not None:
            self.backend: BaseRateLimiter = RedisRateLimiter(redis_client)
        else:
            effective_redis_url = redis_url or os.getenv("REDIS_URL")
            if effective_redis_url and redis is not None:
                try:
                    r_client = redis.from_url(effective_redis_url, decode_responses=True)
                    r_client.ping()
                    self.backend = RedisRateLimiter(r_client)
                    logger.info("Configured Redis-backed rate limiter at %s", effective_redis_url)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to connect to Redis at %s (%s); falling back to in-memory rate limiter",
                        effective_redis_url,
                        exc,
                    )
                    self.backend = InMemoryRateLimiter()
            else:
                self.backend = InMemoryRateLimiter()

    def get_rate_limit_key(self, request: Request) -> str:
        # Keyed by subject if authenticated
        identity = authenticate_request(request)
        if identity and identity.subject and identity.subject != "anonymous":
            return f"sub:{identity.subject}"

        # Otherwise keyed by client IP
        client_ip = get_client_ip(request, self.trusted_proxies)
        return f"ip:{client_ip}"

    def check(
        self,
        request: Request,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        limit = max_requests if max_requests is not None else self.max_requests
        window = window_seconds if window_seconds is not None else self.window_seconds

        key = self.get_rate_limit_key(request)
        allowed, retry_after = self.backend.is_allowed(key, limit, window)

        if not allowed:
            RATE_LIMIT_REJECTIONS.inc()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too Many Requests. Rate limit exceeded.",
                headers={"Retry-After": str(retry_after)},
            )

    async def __call__(self, request: Request) -> None:
        self.check(request)

