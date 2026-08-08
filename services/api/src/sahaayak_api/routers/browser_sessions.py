"""Login-free browser session issuance."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from sahaayak_api.browser_auth import new_access_token, token_digest
from sahaayak_api.rate_limit import apply_rate_limit_headers, enforce_rate_limit
from sahaayak_common import (
    Language,
    State,
    UserSession,
    get_session,
    language_rollout_enabled,
    new_id,
    settings,
    state_rollout_enabled,
)

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

    # A fresh opaque cohort key makes percentage rollout deterministic for the
    # lifetime of this guest session without using an IP address as identity.
    rollout_subject = new_id("cohort")
    state_code = _active_state(
        db,
        payload.state_code or settings.default_state,
        subject=rollout_subject,
    )
    language_code = _active_language(
        db,
        payload.language_code or settings.default_language,
        subject=rollout_subject,
        state_code=state_code,
    )
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


def _active_language(
    db: Session,
    requested: str,
    *,
    subject: str,
    state_code: str,
) -> str:
    normalized = requested.strip().lower()
    row = db.get(Language, normalized)
    if row is not None and _language_available(row, subject=subject, state_code=state_code):
        return row.code
    fallback = db.get(Language, settings.default_language)
    if fallback is not None and _language_available(
        fallback, subject=subject, state_code=state_code
    ):
        return fallback.code
    for candidate in db.exec(select(Language).order_by(Language.code)).all():
        if _language_available(candidate, subject=subject, state_code=state_code):
            return candidate.code
    return settings.default_language


def _active_state(db: Session, requested: str, *, subject: str) -> str:
    normalized = requested.strip().upper()
    row = db.get(State, normalized)
    if row is not None and state_rollout_enabled(row.code, subject=subject):
        return row.code
    fallback = db.get(State, settings.default_state)
    if fallback is not None and state_rollout_enabled(fallback.code, subject=subject):
        return fallback.code
    for candidate in db.exec(select(State).order_by(State.code)).all():
        if state_rollout_enabled(candidate.code, subject=subject):
            return candidate.code
    return settings.default_state


def _language_available(row: Language, *, subject: str, state_code: str) -> bool:
    # Every locale must be explicitly activated in the admin release gate. The
    # feature flag then provides the reversible cohort-level rollout control.
    enabled = language_rollout_enabled(
        row.code,
        subject=subject,
        state_code=state_code,
    )
    return enabled and row.is_active
