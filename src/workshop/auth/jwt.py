"""JWT verification using the platform's existing signing key or JWKS endpoint.

The NestJS HRMS server forwards the user's JWT. This service verifies it and
extracts `sub`, `tenant_id`, and global roles. No new auth system is built.
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from workshop.auth.models import AuthenticatedUser
from workshop.common.errors import ForbiddenError
from workshop.settings import Settings, get_settings

_TENANT_CLAIMS = ("tenant_id", "tenantId", "tenant")
_ROLE_CLAIMS = ("roles", "global_roles", "role")


@lru_cache
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url)


def _resolve_key(token: str, settings: Settings) -> Any:
    if settings.jwt_jwks_url:
        signing_key = _jwks_client(settings.jwt_jwks_url).get_signing_key_from_jwt(token)
        return signing_key.key
    return settings.jwt_secret


def decode_token(token: str) -> AuthenticatedUser:
    settings = get_settings()
    try:
        key = _resolve_key(token, settings)
        claims = jwt.decode(
            token,
            key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"verify_aud": settings.jwt_audience is not None},
        )
    except jwt.PyJWTError as exc:  # pragma: no cover - exercised via integration
        raise ForbiddenError(f"Invalid token: {exc}") from exc

    try:
        user_id = uuid.UUID(str(claims["sub"]))
    except (KeyError, ValueError) as exc:
        raise ForbiddenError("Token is missing a valid subject") from exc

    tenant_value = next((claims[c] for c in _TENANT_CLAIMS if claims.get(c)), None)
    if not tenant_value:
        raise ForbiddenError("Token is missing a tenant claim")
    try:
        tenant_id = uuid.UUID(str(tenant_value))
    except ValueError as exc:
        raise ForbiddenError("Token tenant claim is not a valid identifier") from exc

    roles: set[str] = set()
    for claim in _ROLE_CLAIMS:
        value = claims.get(claim)
        if isinstance(value, str):
            roles.add(value)
        elif isinstance(value, list):
            roles.update(str(v) for v in value)

    return AuthenticatedUser(user_id=user_id, tenant_id=tenant_id, global_roles=frozenset(roles))
