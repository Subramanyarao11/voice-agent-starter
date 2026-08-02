"""Small, fail-closed workforce boundary for the local admin console.

This is intentionally a deployment seam, not a claim that static API tokens
replace managed OIDC + MFA in production. The important property today is that
admin routes are never anonymous and the browser never receives a secret from
the server. Staging can map multiple deployment tokens to least-privilege roles
through ``ADMIN_TOKENS_JSON``.
"""

from __future__ import annotations

import hmac
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from sahaayak_common import get_logger, settings

log = get_logger(__name__)

ROLE_ORDER = {"observer": 10, "operator": 20, "reviewer": 20, "admin": 30}


@dataclass(frozen=True)
class AdminPrincipal:
    actor_id: str
    role: str


def _configured_tokens() -> list[tuple[str, AdminPrincipal]]:
    configured: list[tuple[str, AdminPrincipal]] = []
    if settings.admin_api_token.strip():
        configured.append(
            (
                settings.admin_api_token.strip(),
                AdminPrincipal(actor_id="local-admin", role="admin"),
            )
        )

    raw = settings.admin_tokens_json.strip()
    if not raw:
        return configured
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("admin_tokens_invalid_json", error=str(exc))
        return configured
    if not isinstance(payload, dict):
        log.error("admin_tokens_invalid_shape")
        return configured

    for token, descriptor in payload.items():
        if not isinstance(token, str) or not token.strip():
            continue
        role = "observer"
        actor_id = f"token-{len(configured) + 1}"
        if isinstance(descriptor, str):
            role = descriptor
        elif isinstance(descriptor, dict):
            role = str(descriptor.get("role", role))
            actor_id = str(descriptor.get("actor_id", actor_id))
        if role not in ROLE_ORDER:
            log.warning("admin_token_role_invalid", role=role, actor_id=actor_id)
            continue
        configured.append((token, AdminPrincipal(actor_id=actor_id, role=role)))
    return configured


def _extract_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return request.headers.get("X-Admin-Token", "").strip()


async def get_admin_principal(request: Request) -> AdminPrincipal:
    configured = _configured_tokens()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication is not configured",
        )

    supplied = _extract_token(request)
    if not supplied:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="An admin bearer token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    for expected, principal in configured:
        if hmac.compare_digest(supplied, expected):
            return principal

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="The admin token is not valid for this deployment",
    )


def require_admin_role(*roles: str) -> Callable[..., Any]:
    """Create a FastAPI dependency requiring one of the supplied roles."""

    allowed = set(roles)

    async def dependency(
        principal: AdminPrincipal = Depends(get_admin_principal),
    ) -> AdminPrincipal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This admin action requires a different role",
            )
        return principal

    return dependency
