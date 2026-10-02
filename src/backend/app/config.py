"""
Application configuration for EdiPro backend.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class AuthSettings:
    environment: str = "development"
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_client_id: str | None = None
    oidc_authorize_url: str | None = None
    oidc_token_url: str | None = None
    role_claim: str = "roles"
    api_keys: dict[str, str] = field(default_factory=dict)  # key -> role

    @classmethod
    def from_env(cls) -> AuthSettings:
        env = os.getenv("ENVIRONMENT") or os.getenv("ENV") or "development"
        issuer = os.getenv("OIDC_ISSUER")
        audience = os.getenv("OIDC_AUDIENCE")
        jwks_url = os.getenv("OIDC_JWKS_URL")
        client_id = os.getenv("OIDC_CLIENT_ID")
        authorize_url = os.getenv("OIDC_AUTHORIZE_URL")
        token_url = os.getenv("OIDC_TOKEN_URL")
        role_claim = os.getenv("ROLE_CLAIM", "roles")

        api_keys: dict[str, str] = {}
        # Parse EDI_API_KEYS (comma-separated list of key:role or key)
        raw_keys = os.getenv("EDI_API_KEYS", "")
        if raw_keys:
            for item in raw_keys.split(","):
                item = item.strip()
                if not item:
                    continue
                if ":" in item:
                    k, r = item.split(":", 1)
                    api_keys[k.strip()] = r.strip()
                else:
                    api_keys[item] = "operator"

        # Support single EDI_API_KEY
        single_key = os.getenv("EDI_API_KEY", "").strip()
        if single_key and single_key not in api_keys:
            api_keys[single_key] = "operator"

        return cls(
            environment=env.lower(),
            oidc_issuer=issuer.strip() if issuer else None,
            oidc_audience=audience.strip() if audience else None,
            oidc_jwks_url=jwks_url.strip() if jwks_url else None,
            oidc_client_id=client_id.strip() if client_id else None,
            oidc_authorize_url=authorize_url.strip() if authorize_url else None,
            oidc_token_url=token_url.strip() if token_url else None,
            role_claim=role_claim,
            api_keys=api_keys,
        )

    @property
    def is_configured(self) -> bool:
        """True if either OIDC or API-key auth is configured."""
        return bool(self.oidc_jwks_url or self.oidc_issuer or self.api_keys)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"
