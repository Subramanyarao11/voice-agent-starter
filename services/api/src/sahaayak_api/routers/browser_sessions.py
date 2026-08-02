"""Login-free browser session issuance."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from sahaayak_api.browser_auth import new_access_token, token_digest
from sahaayak_api.rate_limit import apply_rate_limit_headers, enforce_rate_limit
from sahaayak_common import Language, State, UserSession, get_session, new_id, settings

router = APIRouter(prefix="/api/browser-sessions", tags=["browser sessions"])


class BrowserSessionRequest(BaseModel):
    language_code: str | None = Field(default=None, min_length=2, max_length=16)
    state_code: str | None = Field(default=None, min_length=2, max_length=16)


class BrowserSessionOut(BaseModel):
    session_id: str
    access_token: str
    language_code: str
    state_code: str
    expires_at: datetime


@router.post("", response_model=BrowserSessionOut, status_code=status.HTTP_201_CREATED)
async def create_browser_session(
    payload: BrowserSessionRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
) -> BrowserSessionOut:
    decision = await enforce_rate_limit(request, session_id=None, bucket="session_create")
    apply_rate_limit_headers(response, decision)

    language_code = _active_language(db, payload.language_code or settings.default_language)
    state_code = _active_state(db, payload.state_code or settings.default_state)
    public_session_id = new_id("ses")
    access_token = new_access_token()
    expires_at = datetime.now(UTC) + timedelta(hours=max(1, settings.guest_session_ttl_hours))
    row = UserSession(
        id=public_session_id,
        phone_or_session_id=f"browser:{public_session_id}",
        access_token_hash=token_digest(access_token),
        auth_mode="guest",
        expires_at=expires_at,
        state_code=state_code,
        language_code=language_code,
    )
    db.add(row)
    db.commit()
    return BrowserSessionOut(
        session_id=public_session_id,
        access_token=access_token,
        language_code=language_code,
        state_code=state_code,
        expires_at=expires_at,
    )


def _active_language(db: Session, requested: str) -> str:
    row = db.exec(
        select(Language).where(Language.code == requested, Language.is_active.is_(True))
    ).first()
    if row is not None:
        return row.code
    fallback = db.exec(
        select(Language).where(
            Language.code == settings.default_language,
            Language.is_active.is_(True),
        )
    ).first()
    return fallback.code if fallback is not None else requested


def _active_state(db: Session, requested: str) -> str:
    row = db.exec(select(State).where(State.code == requested, State.is_active.is_(True))).first()
    if row is not None:
        return row.code
    fallback = db.exec(
        select(State).where(State.code == settings.default_state, State.is_active.is_(True))
    ).first()
    return fallback.code if fallback is not None else requested
