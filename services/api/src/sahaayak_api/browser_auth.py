"""Server-owned anonymous browser sessions.

The browser remains login-free, but every sensitive operation is authorized by
an opaque bearer token issued by Sahaayak. Only its hash is stored in the
database, so changing a public session ID cannot reveal another caller's data.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, select

from sahaayak_common import UserSession, get_session


@dataclass(frozen=True)
class BrowserSessionPrincipal:
    session_id: str
    caller_id: str
    language_code: str
    state_code: str
    expires_at: datetime | None


def new_access_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def extract_browser_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def principal_for_row(row: UserSession) -> BrowserSessionPrincipal:
    return BrowserSessionPrincipal(
        session_id=row.id,
        caller_id=row.phone_or_session_id,
        language_code=row.language_code,
        state_code=row.state_code,
        expires_at=row.expires_at,
    )


def principal_for_access_token(
    db: Session, token: str
) -> BrowserSessionPrincipal | None:
    """Resolve a server-issued guest token for non-HTTP transports."""
    if not token.strip():
        return None
    row = db.exec(
        select(UserSession).where(
            UserSession.access_token_hash == token_digest(token),
            UserSession.auth_mode == "guest",
        )
    ).first()
    if row is None or _expired(row.expires_at):
        return None
    return principal_for_row(row)


async def require_browser_session(
    request: Request,
    db: Session = Depends(get_session),
) -> BrowserSessionPrincipal:
    token = extract_browser_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A guest session bearer token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    row = db.exec(
        select(UserSession).where(
            UserSession.access_token_hash == token_digest(token),
            UserSession.auth_mode == "guest",
        )
    ).first()
    if row is None or _expired(row.expires_at):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This guest session has expired. Start a new session.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal_for_row(row)


def _expired(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC)
