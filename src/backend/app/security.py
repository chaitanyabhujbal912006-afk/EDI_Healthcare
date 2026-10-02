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
import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import jwt
from fastapi import Header, HTTPException, Request, status

from app.config import AuthSettings

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
