"""Consent-bound Assisted Saathi sessions.

This is the first delegated-access slice. It deliberately exposes an
invitation path for an authenticated citizen account, not a general-purpose
helper proxy. A helper can redeem a single-use capability, but the server
does not grant a projection until the citizen confirms the purpose. Some
confirmed actions now call narrowly allowlisted application and escalation
services; other action keys remain explicitly ledger-only until integrated.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from sahaayak_api.admin_auth import AdminPrincipal, require_admin_role
from sahaayak_api.citizen_auth import (
    CitizenPrincipal,
    get_or_create_citizen_account,
    require_citizen,
)
from sahaayak_api.rate_limit import apply_rate_limit_headers, enforce_rate_limit
from sahaayak_api.routers.applications import apply_assisted_application_status
from sahaayak_api.routers.saved_benefits import ensure_application_tasks
from sahaayak_api.telemetry import make_audit_event
from sahaayak_common import (
    ApplicationCase,
    ApplicationDataEncryptionUnavailable,
    ApplicationStatusEvent,
    AssistanceAction,
    AssistanceConsent,
    AssistanceSession,
    Benefit,
    DepartmentDirectoryEntry,
    EscalationTicket,
    Household,
    HouseholdConsentEvent,
    HouseholdMember,
    Language,
    UserSession,
    benefit_snapshot,
    decrypt_reference,
    encrypt_reference,
    get_session,
    mask_reference,
    new_id,
    normalize_reference,
    reference_hash,
    resolve_escalation_route,
    settings,
    ticket_id,
)
from sahaayak_contracts import VerificationStatus

router = APIRouter(prefix="/api", tags=["assisted saathi"])

ASSISTANCE_PURPOSES = {
    "discover_benefits",
    "prepare_application",
    "record_application_reference",
    "contact_department",
    "create_escalation",
    "print_application_pack",
    "language_or_accessibility_help",
}

PURPOSE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "discover_benefits": ("public_catalog", "eligibility_explanation"),
    "prepare_application": (
        "public_catalog",
        "application_requirements",
        "application_draft",
    ),
    "record_application_reference": ("application_requirements",),
    "contact_department": ("department_directory",),
    "create_escalation": ("public_catalog", "department_directory"),
    "print_application_pack": (
        "public_catalog",
        "application_requirements",
        "print_preview",
    ),
    "language_or_accessibility_help": ("public_catalog", "language_preferences"),
}

PURPOSE_ACTIONS: dict[str, tuple[str, ...]] = {
    "discover_benefits": ("review_public_benefit",),
    "prepare_application": ("prepare_application",),
    "record_application_reference": ("record_application_reference",),
    "contact_department": ("contact_department",),
    "create_escalation": ("create_escalation",),
    "print_application_pack": ("print_application_pack",),
    "language_or_accessibility_help": ("language_or_accessibility_help",),
}

_ALLOWED_TARGET_TYPES = {"", "benefit", "application_case", "department", "language"}
_TERMINAL_STATES = {"completed", "revoked", "expired", "cancelled", "policy_terminated"}
_ACTIVE_STATES = {"active", "paused"}
_TOKEN_BYTES = 32
_APPLICATION_ACTION_STATUSES = {
    "submitted",
    "acknowledged",
    "under_review",
    "action_required",
    "approved",
    "delivered",
    "rejected",
    "withdrawn",
}


class AssistanceInvitationCreate(BaseModel):
    purpose: str = Field(min_length=1, max_length=64)
    data_categories: list[str] = Field(default_factory=list, max_length=8)
    household_id: str | None = Field(default=None, max_length=160)
    household_member_id: str | None = Field(default=None, max_length=160)
    locale: str = Field(default="en", min_length=2, max_length=16)
    expires_in_minutes: int | None = Field(default=None, ge=1, le=60)


class AssistanceInvitationOut(BaseModel):
    id: str
    invitation_token: str
    status: str
    purpose: str
    approved_data_categories: list[str]
    allowed_action_keys: list[str]
    locale: str
    notice_version: str
    expires_at: datetime


class AssistanceSessionOut(BaseModel):
    id: str
    purpose: str
    status: str
    approved_data_categories: list[str]
    allowed_action_keys: list[str]
    locale: str
    helper_actor_id: str | None = None
    helper_org_id: str = ""
    expires_at: datetime
    last_activity_at: datetime
    created_at: datetime
    consented_at: datetime | None = None
    ended_at: datetime | None = None
    revision: int
    projection: dict = Field(default_factory=dict)


class AssistanceConsentRequest(BaseModel):
    confirm: bool = False
    locale: str | None = Field(default=None, min_length=2, max_length=16)
    confirmation_mode: Literal["citizen_affirmed"] = "citizen_affirmed"


class AssistanceRedeemRequest(BaseModel):
    invitation_token: str = Field(min_length=32, max_length=256)


class AssistanceActionCreate(BaseModel):
    action_key: str = Field(min_length=1, max_length=80)
    target_type: str = Field(default="", max_length=40)
    target_id: str = Field(default="", max_length=160)
    preview_code: str = Field(default="ready_for_citizen_review", max_length=80)
    application_status: str = Field(default="submitted", max_length=40)
    submission_date: date | None = None
    external_reference: str | None = Field(default=None, max_length=160)
    reason_code: str = Field(default="assisted_saathi", max_length=80)
    idempotency_key: str = Field(min_length=8, max_length=160)


class AssistanceActionConfirm(BaseModel):
    confirm: bool = False
    confirmation_mode: Literal["citizen_affirmed"] = "citizen_affirmed"


class AssistanceActionOut(BaseModel):
    id: str
    action_key: str
    target_type: str
    target_id: str
    stage: str
    preview_code: str
    effect_code: str = ""
    effect_reference_masked: str = ""
    effect_record_id: str = ""
    confirmation_mode: str
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


class AssistanceReceiptOut(BaseModel):
    id: str
    status: str
    purpose: str
    helper_actor_id: str | None = None
    helper_org_id: str = ""
    created_at: datetime
    ended_at: datetime | None = None
    actions: list[AssistanceActionOut]


@router.post(
    "/assistance/invitations",
    response_model=AssistanceInvitationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_assistance_invitation(
    payload: AssistanceInvitationCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> AssistanceInvitationOut:
    account = get_or_create_citizen_account(db, principal)
    decision = await enforce_rate_limit(request, session_id=account.id, bucket="assistance")
    apply_rate_limit_headers(response, decision)
    purpose = _validate_purpose(payload.purpose)
    categories = _validate_categories(purpose, payload.data_categories)
    household, member = _owned_subject(
        db,
        account_id=account.id,
        household_id=payload.household_id,
        household_member_id=payload.household_member_id,
    )
    citizen_session = _ensure_citizen_session(
        db,
        account_id=account.id,
        state_code=household.state_code if household else "KA",
        language_code=payload.locale,
    )
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    now = datetime.now(UTC)
    configured_ttl = max(1, settings.assistance_invitation_ttl_minutes)
    ttl_minutes = min(payload.expires_in_minutes or configured_ttl, configured_ttl)
    row = AssistanceSession(
        id=new_id("assist"),
        invitation_token_hash=_token_hash(token),
        citizen_session_id=citizen_session.id,
        citizen_account_id=account.id,
        household_id=household.id if household else None,
        household_member_id=member.id if member else None,
        purpose=purpose,
        approved_data_categories=categories,
        allowed_action_keys=list(PURPOSE_ACTIONS[purpose]),
        projection_version=settings.assistance_notice_version,
        locale=payload.locale.strip().lower(),
        expires_at=now + timedelta(minutes=ttl_minutes),
        last_activity_at=now,
        created_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _invitation_out(row, token=token)


@router.get(
    "/assistance/invitations/{assistance_id}",
    response_model=AssistanceSessionOut,
)
def get_assistance_invitation(
    assistance_id: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> AssistanceSessionOut:
    row, account = _citizen_session(db, assistance_id, principal)
    _expire_if_needed(db, row)
    db.commit()
    return _session_out(row, include_projection=False)


@router.post(
    "/assistance/invitations/{assistance_id}/consent",
    response_model=AssistanceSessionOut,
)
def consent_to_assistance(
    assistance_id: str,
    payload: AssistanceConsentRequest,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> AssistanceSessionOut:
    row, account = _citizen_session(db, assistance_id, principal)
    _expire_if_needed(db, row)
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Citizen confirmation is required")
    if row.status != "awaiting_citizen_consent":
        raise HTTPException(
            status_code=409,
            detail="This assistance invitation is not awaiting consent",
        )

    now = datetime.now(UTC)
    row.status = "active"
    row.consented_at = now
    row.last_activity_at = now
    row.revision += 1
    db.add(row)
    _record_consent(db, row, account_id=account.id, principal=principal, action="granted")
    db.commit()
    db.refresh(row)
    return _session_out(row, include_projection=False)


@router.get(
    "/assistance/sessions/{assistance_id}",
    response_model=AssistanceSessionOut,
)
def get_citizen_assistance_session(
    assistance_id: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> AssistanceSessionOut:
    row, _account = _citizen_session(db, assistance_id, principal)
    _expire_if_needed(db, row)
    db.commit()
    return _session_out(row, include_projection=False)


@router.post(
    "/assistance/sessions/{assistance_id}/revoke",
    response_model=AssistanceSessionOut,
)
def revoke_assistance(
    assistance_id: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> AssistanceSessionOut:
    row, account = _citizen_session(db, assistance_id, principal)
    _expire_if_needed(db, row)
    if row.status in _TERMINAL_STATES:
        return _session_out(row, include_projection=False)
    now = datetime.now(UTC)
    row.status = "revoked"
    row.ended_at = now
    row.last_activity_at = now
    row.revision += 1
    db.add(row)
    _record_consent(db, row, account_id=account.id, principal=principal, action="withdrawn")
    db.commit()
    db.refresh(row)
    return _session_out(row, include_projection=False)


@router.post(
    "/assistance/sessions/{assistance_id}/resume",
    response_model=AssistanceSessionOut,
)
def resume_assistance(
    assistance_id: str,
    payload: AssistanceConsentRequest,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> AssistanceSessionOut:
    row, account = _citizen_session(db, assistance_id, principal)
    _expire_if_needed(db, row)
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Citizen confirmation is required")
    if row.status != "paused":
        raise HTTPException(status_code=409, detail="This assistance session is not paused")
    now = datetime.now(UTC)
    row.status = "active"
    row.last_activity_at = now
    row.revision += 1
    db.add(row)
    _record_consent(db, row, account_id=account.id, principal=principal, action="granted")
    db.commit()
    db.refresh(row)
    return _session_out(row, include_projection=False)


@router.get(
    "/assistance/sessions/{assistance_id}/receipt",
    response_model=AssistanceReceiptOut,
)
def assistance_receipt(
    assistance_id: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> AssistanceReceiptOut:
    row, _account = _citizen_session(db, assistance_id, principal)
    _expire_if_needed(db, row)
    actions = db.exec(
        select(AssistanceAction)
        .where(AssistanceAction.assistance_session_id == row.id)
        .order_by(AssistanceAction.created_at)
    ).all()
    db.commit()
    return AssistanceReceiptOut(
        id=row.id,
        status=row.status,
        purpose=row.purpose,
        helper_actor_id=row.helper_actor_id,
        helper_org_id=row.helper_org_id,
        created_at=row.created_at,
        ended_at=row.ended_at,
        actions=[_action_out(action) for action in actions],
    )


@router.get(
    "/assistance/sessions/{assistance_id}/actions",
    response_model=list[AssistanceActionOut],
)
def list_citizen_assistance_actions(
    assistance_id: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> list[AssistanceActionOut]:
    row, _account = _citizen_session(db, assistance_id, principal)
    _expire_if_needed(db, row)
    actions = db.exec(
        select(AssistanceAction)
        .where(AssistanceAction.assistance_session_id == row.id)
        .order_by(AssistanceAction.created_at)
    ).all()
    db.commit()
    return [_action_out(action) for action in actions]


@router.post(
    "/assistant/invitations/redeem",
    response_model=AssistanceSessionOut,
)
async def redeem_assistance_invitation(
    payload: AssistanceRedeemRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("assistant", "admin")),
) -> AssistanceSessionOut:
    decision = await enforce_rate_limit(
        request,
        session_id=_token_hash(payload.invitation_token),
        bucket="assistance",
    )
    apply_rate_limit_headers(response, decision)
    row = db.exec(
        select(AssistanceSession).where(
            AssistanceSession.invitation_token_hash == _token_hash(payload.invitation_token)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No usable assistance invitation")
    _expire_if_needed(db, row)
    if row.status != "invited":
        raise HTTPException(
            status_code=409,
            detail="This assistance invitation is no longer usable",
        )
    if principal.auth_source == "oidc" and not principal.organization_id:
        raise HTTPException(
            status_code=403,
            detail="The helper identity has no registered organization",
        )
    now = datetime.now(UTC)
    row.helper_actor_id = principal.actor_id[:120]
    row.helper_org_id = (principal.organization_id or "local")[:160]
    row.status = "awaiting_citizen_consent"
    row.last_activity_at = now
    row.revision += 1
    db.add(row)
    db.add(
        make_audit_event(
            principal=principal,
            action="assistance.invitation.redeem",
            target_type="assistance_session",
            target_id=row.id,
            reason="Redeemed a single-use citizen assistance invitation",
            safe_before={"status": "invited"},
            safe_after={"status": row.status, "purpose": row.purpose},
        )
    )
    db.commit()
    db.refresh(row)
    return _session_out(row, include_projection=False)


@router.get(
    "/assistant/sessions/{assistance_id}",
    response_model=AssistanceSessionOut,
)
def get_helper_assistance_session(
    assistance_id: str,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("assistant", "admin")),
) -> AssistanceSessionOut:
    row = _helper_session(db, assistance_id, principal)
    _expire_if_needed(db, row)
    db.commit()
    return _session_out(row, include_projection=row.status == "active")


@router.get(
    "/assistant/sessions/{assistance_id}/actions",
    response_model=list[AssistanceActionOut],
)
def list_helper_assistance_actions(
    assistance_id: str,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("assistant", "admin")),
) -> list[AssistanceActionOut]:
    row = _helper_session(db, assistance_id, principal)
    _expire_if_needed(db, row)
    actions = db.exec(
        select(AssistanceAction)
        .where(AssistanceAction.assistance_session_id == row.id)
        .order_by(AssistanceAction.created_at)
    ).all()
    db.commit()
    return [_action_out(action) for action in actions]


@router.post(
    "/assistant/sessions/{assistance_id}/draft-actions",
    response_model=AssistanceActionOut,
    status_code=status.HTTP_201_CREATED,
)
async def draft_assistance_action(
    assistance_id: str,
    payload: AssistanceActionCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("assistant", "admin")),
) -> AssistanceActionOut:
    row = _helper_session(db, assistance_id, principal)
    decision = await enforce_rate_limit(request, session_id=row.id, bucket="assistance")
    apply_rate_limit_headers(response, decision)
    _require_active(row)
    _validate_action(
        row,
        payload.action_key,
        payload.target_type,
        payload.target_id,
        payload.preview_code,
        payload.application_status,
    )
    (
        requested_reference_ciphertext,
        requested_reference_hash,
        requested_reference_masked,
    ) = _prepare_requested_reference(payload)
    existing = db.exec(
        select(AssistanceAction).where(
            AssistanceAction.assistance_session_id == row.id,
            AssistanceAction.idempotency_key == payload.idempotency_key,
        )
    ).first()
    if existing is not None:
        return _action_out(existing)
    now = datetime.now(UTC)
    action = AssistanceAction(
        id=new_id("assist-action"),
        assistance_session_id=row.id,
        action_key=payload.action_key,
        target_type=payload.target_type,
        target_id=payload.target_id,
        stage="drafted",
        helper_actor_id=principal.actor_id[:120],
        safe_preview={
            "preview_code": payload.preview_code,
            "application_status": payload.application_status
            if payload.action_key == "record_application_reference"
            else "",
            "submission_date": payload.submission_date.isoformat()
            if payload.submission_date
            else "",
            "has_external_reference": bool(payload.external_reference),
            "reason_code": payload.reason_code.strip(),
        },
        requested_reference_ciphertext=requested_reference_ciphertext,
        requested_reference_hash=requested_reference_hash,
        requested_reference_masked=requested_reference_masked,
        before_safe_hash=_safe_hash({"stage": "drafted", "action_key": payload.action_key}),
        idempotency_key=payload.idempotency_key,
        created_at=now,
        updated_at=now,
    )
    row.last_activity_at = now
    row.revision += 1
    db.add(action)
    db.add(row)
    db.add(
        make_audit_event(
            principal=principal,
            action="assistance.action.draft",
            target_type="assistance_action",
            target_id=action.id,
            reason="Created a purpose-bound action draft",
            safe_before={"stage": "none"},
            safe_after={"stage": action.stage, "action_key": action.action_key},
        )
    )
    db.commit()
    db.refresh(action)
    return _action_out(action)


@router.post(
    "/assistance/sessions/{assistance_id}/actions/{action_id}/confirm",
    response_model=AssistanceActionOut,
)
def confirm_assistance_action(
    assistance_id: str,
    action_id: str,
    payload: AssistanceActionConfirm,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> AssistanceActionOut:
    row, account = _citizen_session(db, assistance_id, principal)
    _expire_if_needed(db, row)
    _require_active(row)
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Citizen confirmation is required")
    action = _get_action(db, row.id, action_id)
    if action.stage == "citizen_confirmed":
        return _action_out(action)
    if action.stage != "drafted":
        raise HTTPException(status_code=409, detail="This action cannot be confirmed")
    now = datetime.now(UTC)
    action.stage = "citizen_confirmed"
    action.confirmation_actor_hash = principal.subject_hash
    action.confirmation_mode = payload.confirmation_mode
    action.updated_at = now
    row.last_activity_at = now
    row.revision += 1
    db.add(action)
    db.add(row)
    db.add(
        HouseholdConsentEvent(
            id=new_id("hconsent"),
            citizen_account_id=account.id,
            household_id=row.household_id,
            household_member_id=row.household_member_id,
            purpose=f"assistance_action:{row.purpose}",
            action="granted",
            notice_version=row.projection_version,
            locale=row.locale,
            actor_id="citizen",
            assistance_session_id=row.id,
            safe_context={"action_key": action.action_key, "action_id": action.id},
            created_at=now,
        )
    )
    db.commit()
    db.refresh(action)
    return _action_out(action)


@router.post(
    "/assistant/sessions/{assistance_id}/actions/{action_id}/execute",
    response_model=AssistanceActionOut,
)
def execute_assistance_action(
    assistance_id: str,
    action_id: str,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("assistant", "admin")),
) -> AssistanceActionOut:
    row = _helper_session(db, assistance_id, principal)
    _require_active(row)
    action = _get_action(db, row.id, action_id)
    if action.stage == "executed":
        return _action_out(action)
    if action.stage != "citizen_confirmed":
        raise HTTPException(
            status_code=409,
            detail="Citizen confirmation is required before this action can execute",
        )
    effect = _execute_downstream_effect(db, row, action, principal)
    now = datetime.now(UTC)
    action.stage = "executed"
    action.safe_preview = {**action.safe_preview, **effect}
    action.after_safe_hash = _safe_hash(
        {"stage": "executed", "action_key": action.action_key, "action_id": action.id}
    )
    action.updated_at = now
    row.last_activity_at = now
    row.revision += 1
    db.add(action)
    db.add(row)
    db.add(
        make_audit_event(
            principal=principal,
            action="assistance.action.execute",
            target_type="assistance_action",
            target_id=action.id,
            reason="Executed a citizen-confirmed downstream action",
            safe_before={"stage": "citizen_confirmed"},
            safe_after={
                "stage": "executed",
                "effect": effect.get("effect_code", "ledger_only"),
                "record_id": effect.get("effect_record_id", ""),
            },
        )
    )
    db.commit()
    db.refresh(action)
    return _action_out(action)


@router.post(
    "/assistant/sessions/{assistance_id}/pause",
    response_model=AssistanceSessionOut,
)
def pause_assistance(
    assistance_id: str,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("assistant", "admin")),
) -> AssistanceSessionOut:
    row = _helper_session(db, assistance_id, principal)
    _require_active(row)
    now = datetime.now(UTC)
    row.status = "paused"
    row.last_activity_at = now
    row.revision += 1
    db.add(row)
    db.add(
        make_audit_event(
            principal=principal,
            action="assistance.session.pause",
            target_type="assistance_session",
            target_id=row.id,
            reason="Paused the helper projection",
            safe_before={"status": "active"},
            safe_after={"status": "paused"},
        )
    )
    db.commit()
    db.refresh(row)
    return _session_out(row, include_projection=False)


@router.post(
    "/assistant/sessions/{assistance_id}/complete",
    response_model=AssistanceReceiptOut,
)
def complete_assistance(
    assistance_id: str,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("assistant", "admin")),
) -> AssistanceReceiptOut:
    row = _helper_session(db, assistance_id, principal)
    if row.status not in _ACTIVE_STATES:
        raise HTTPException(status_code=409, detail="This assistance session is not active")
    now = datetime.now(UTC)
    row.status = "completed"
    row.ended_at = now
    row.last_activity_at = now
    row.revision += 1
    db.add(row)
    db.add(
        make_audit_event(
            principal=principal,
            action="assistance.session.complete",
            target_type="assistance_session",
            target_id=row.id,
            reason="Completed the time-bound assistance session",
            safe_before={"status": "active"},
            safe_after={"status": "completed"},
        )
    )
    actions = db.exec(
        select(AssistanceAction)
        .where(AssistanceAction.assistance_session_id == row.id)
        .order_by(AssistanceAction.created_at)
    ).all()
    db.commit()
    return AssistanceReceiptOut(
        id=row.id,
        status=row.status,
        purpose=row.purpose,
        helper_actor_id=row.helper_actor_id,
        helper_org_id=row.helper_org_id,
        created_at=row.created_at,
        ended_at=row.ended_at,
        actions=[_action_out(action) for action in actions],
    )


def _validate_purpose(value: str) -> str:
    purpose = value.strip()
    if purpose not in ASSISTANCE_PURPOSES:
        raise HTTPException(status_code=400, detail="The assistance purpose is not allowed")
    return purpose


def _validate_categories(purpose: str, requested: list[str]) -> list[str]:
    allowed = set(PURPOSE_CATEGORIES[purpose])
    categories = [item.strip() for item in requested if item.strip()]
    if not categories:
        return list(PURPOSE_CATEGORIES[purpose])
    if len(set(categories)) != len(categories) or any(item not in allowed for item in categories):
        raise HTTPException(
            status_code=400,
            detail="The requested data category is outside the declared purpose",
        )
    return categories


def _owned_subject(
    db: Session,
    *,
    account_id: str,
    household_id: str | None,
    household_member_id: str | None,
) -> tuple[Household | None, HouseholdMember | None]:
    if household_member_id and not household_id:
        raise HTTPException(status_code=400, detail="A household is required for a member subject")
    household = None
    if household_id:
        household = db.get(Household, household_id)
        if (
            household is None
            or household.owner_account_id != account_id
            or household.status != "active"
        ):
            raise HTTPException(status_code=404, detail="No such household")
    member = None
    if household_member_id:
        member = db.get(HouseholdMember, household_member_id)
        if (
            member is None
            or member.household_id != household.id
            or member.status != "active"
        ):
            raise HTTPException(status_code=404, detail="No such household member")
        if member.authority_status in {"required", "rejected"}:
            raise HTTPException(
                status_code=403,
                detail="Citizen authority for this household member is not confirmed",
            )
    return household, member


def _ensure_citizen_session(
    db: Session,
    *,
    account_id: str,
    state_code: str,
    language_code: str,
) -> UserSession:
    existing = db.exec(
        select(UserSession).where(
            UserSession.phone_or_session_id == f"citizen:{account_id}",
            UserSession.auth_mode == "citizen",
        )
    ).first()
    if existing is not None:
        return existing
    normalized_language = language_code.strip().lower()
    if db.get(Language, normalized_language) is None:
        normalized_language = "en"
    row = UserSession(
        id=new_id("citizen-session"),
        phone_or_session_id=f"citizen:{account_id}",
        auth_mode="citizen",
        state_code=state_code or "KA",
        language_code=normalized_language,
        profile={},
        expires_at=None,
    )
    db.add(row)
    db.flush()
    return row


def _citizen_session(
    db: Session,
    assistance_id: str,
    principal: CitizenPrincipal,
) -> tuple[AssistanceSession, object]:
    account = get_or_create_citizen_account(db, principal)
    row = db.get(AssistanceSession, assistance_id)
    if row is None or row.citizen_account_id != account.id:
        raise HTTPException(status_code=404, detail="No such assistance session")
    return row, account


def _helper_session(
    db: Session,
    assistance_id: str,
    principal: AdminPrincipal,
) -> AssistanceSession:
    row = db.get(AssistanceSession, assistance_id)
    if row is None or row.helper_actor_id != principal.actor_id:
        raise HTTPException(status_code=404, detail="No such assistance session")
    return row


def _expire_if_needed(db: Session, row: AssistanceSession) -> None:
    if row.status in _TERMINAL_STATES:
        return
    now = datetime.now(UTC)
    expires_at = _as_utc(row.expires_at)
    idle_cutoff = _as_utc(row.last_activity_at) + timedelta(
        minutes=max(1, settings.assistance_idle_timeout_minutes)
    )
    if now < expires_at and (row.status not in _ACTIVE_STATES or now < idle_cutoff):
        return
    row.status = "expired"
    row.ended_at = now
    row.last_activity_at = now
    row.revision += 1
    db.add(row)
    if row.citizen_account_id:
        db.add(
            AssistanceConsent(
                id=new_id("assist-consent"),
                assistance_session_id=row.id,
                citizen_account_id=row.citizen_account_id,
                action="expired",
                notice_version=row.projection_version,
                locale=row.locale,
                confirmation_mode="system_expiry",
                approved_data_categories=list(row.approved_data_categories),
                approved_action_keys=list(row.allowed_action_keys),
                helper_actor_id=row.helper_actor_id or "",
                helper_org_id=row.helper_org_id,
                created_at=now,
            )
        )


def _record_consent(
    db: Session,
    row: AssistanceSession,
    *,
    account_id: str,
    principal: CitizenPrincipal,
    action: Literal["granted", "withdrawn"],
) -> None:
    db.add(
        AssistanceConsent(
            id=new_id("assist-consent"),
            assistance_session_id=row.id,
            citizen_account_id=account_id,
            action=action,
            notice_version=row.projection_version,
            locale=row.locale,
            confirmation_mode="citizen_affirmed",
            approved_data_categories=list(row.approved_data_categories),
            approved_action_keys=list(row.allowed_action_keys),
            citizen_subject_hash=principal.subject_hash,
            helper_actor_id=row.helper_actor_id or "",
            helper_org_id=row.helper_org_id,
            created_at=datetime.now(UTC),
        )
    )
    db.add(
        HouseholdConsentEvent(
            id=new_id("hconsent"),
            citizen_account_id=account_id,
            household_id=row.household_id,
            household_member_id=row.household_member_id,
            purpose=f"assistance:{row.purpose}",
            action=action,
            notice_version=row.projection_version,
            locale=row.locale,
            actor_id="citizen",
            assistance_session_id=row.id,
            safe_context={
                "data_category_count": len(row.approved_data_categories),
                "action_count": len(row.allowed_action_keys),
            },
            created_at=datetime.now(UTC),
        )
    )


def _require_active(row: AssistanceSession) -> None:
    if row.status != "active":
        raise HTTPException(
            status_code=409,
            detail="Citizen consent is required and the assistance session must be active",
        )


def _validate_action(
    row: AssistanceSession,
    action_key: str,
    target_type: str,
    target_id: str,
    preview_code: str,
    application_status: str,
) -> None:
    if action_key not in row.allowed_action_keys:
        raise HTTPException(status_code=400, detail="This action is outside the session purpose")
    if target_type not in _ALLOWED_TARGET_TYPES:
        raise HTTPException(status_code=400, detail="The action target type is not allowed")
    if action_key == "record_application_reference":
        if target_type != "application_case" or not target_id.strip():
            raise HTTPException(
                status_code=400,
                detail="Recording an application reference needs an application case target",
            )
        if application_status not in _APPLICATION_ACTION_STATUSES:
            raise HTTPException(status_code=400, detail="The application status is not allowed")
    elif action_key == "prepare_application" and (
        target_type != "benefit" or not target_id.strip()
    ):
        raise HTTPException(
            status_code=400,
            detail="Preparing an application needs a benefit target",
        )
    elif application_status != "submitted":
        raise HTTPException(
            status_code=400,
            detail="Application status is only accepted for application reference actions",
        )
    if action_key in {"contact_department", "create_escalation"} and target_type not in {
        "",
        "department",
    }:
        raise HTTPException(status_code=400, detail="A department action needs a department target")
    if not preview_code or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789_.-" for character in preview_code
    ):
        raise HTTPException(status_code=400, detail="The action preview code is not safe")


def _prepare_requested_reference(
    payload: AssistanceActionCreate,
) -> tuple[str | None, str | None, str]:
    if not payload.external_reference:
        return None, None, ""
    if payload.action_key != "record_application_reference":
        raise HTTPException(
            status_code=400,
            detail="An external reference is only accepted for application reference actions",
        )
    try:
        normalized = normalize_reference(payload.external_reference)
        return encrypt_reference(normalized), reference_hash(normalized), mask_reference(normalized)
    except ApplicationDataEncryptionUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="Application reference capture is not configured on this deployment",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _execute_downstream_effect(
    db: Session,
    row: AssistanceSession,
    action: AssistanceAction,
    principal: AdminPrincipal,
) -> dict[str, str]:
    if action.action_key == "prepare_application":
        case = _create_or_get_assisted_application(db, row, action)
        return {
            "effect_code": "application_case_prepared",
            "effect_record_id": case.id,
        }

    if action.action_key == "record_application_reference":
        case = db.get(ApplicationCase, action.target_id)
        if case is None or case.session_id != row.citizen_session_id:
            raise HTTPException(
                status_code=404,
                detail="The application case is not in this citizen session",
            )
        reference = None
        if action.requested_reference_ciphertext:
            try:
                reference = decrypt_reference(action.requested_reference_ciphertext)
            except (ValueError, RuntimeError) as exc:
                raise HTTPException(
                    status_code=503,
                    detail="The application reference cannot be decrypted on this deployment",
                ) from exc
        submission_date_value = str(action.safe_preview.get("submission_date", ""))
        submission_date = (
            date.fromisoformat(submission_date_value) if submission_date_value else None
        )
        status_value = str(action.safe_preview.get("application_status", "submitted"))
        apply_assisted_application_status(
            db,
            case,
            status_value=status_value,  # type: ignore[arg-type]
            occurred_at=None,
            submission_date=submission_date,
            external_reference=reference,
            reason_code=str(action.safe_preview.get("reason_code", "assisted_saathi")),
            actor_id=principal.actor_id,
        )
        return {
            "effect_code": "application_status_recorded",
            "effect_record_id": case.id,
            "effect_reference_masked": action.requested_reference_masked,
        }

    if action.action_key in {"contact_department", "create_escalation"}:
        ticket = _create_assistance_ticket(db, row, action, principal)
        return {
            "effect_code": (
                "department_handoff_recorded"
                if action.action_key == "contact_department"
                else "escalation_ticket_created"
            ),
            "effect_record_id": ticket.id,
        }

    return {"effect_code": "ledger_only", "effect_record_id": ""}


def _create_or_get_assisted_application(
    db: Session,
    row: AssistanceSession,
    action: AssistanceAction,
) -> ApplicationCase:
    if not row.citizen_session_id:
        raise HTTPException(
            status_code=409,
            detail="This assistance session has no citizen application session",
        )
    existing = db.exec(
        select(ApplicationCase)
        .where(
            ApplicationCase.session_id == row.citizen_session_id,
            ApplicationCase.benefit_id == action.target_id,
        )
        .order_by(ApplicationCase.updated_at.desc())
    ).first()
    if existing is not None:
        return existing
    benefit = db.get(Benefit, action.target_id)
    if benefit is None or not benefit.is_active:
        raise HTTPException(status_code=404, detail="The selected benefit is not available")
    if benefit.verification_status is not VerificationStatus.HUMAN_VERIFIED:
        raise HTTPException(
            status_code=409,
            detail="Only a human-verified published benefit can start an application",
        )
    now = datetime.now(UTC)
    source_url = benefit.source_document_url or benefit.source_url
    case = ApplicationCase(
        id=new_id("application"),
        session_id=row.citizen_session_id,
        citizen_account_id=row.citizen_account_id,
        household_member_id=row.household_member_id,
        benefit_id=benefit.id,
        benefit_revision=benefit.content_revision,
        benefit_snapshot={
            **benefit_snapshot(benefit),
            "content_revision": benefit.content_revision,
        },
        application_channel="assisted",
        status="draft",
        status_provenance="system_derived",
        status_recorded_at=now,
        status_source_url=source_url,
        readiness_state="not_ready",
        readiness_blockers=[],
        revision=1,
        created_at=now,
        updated_at=now,
    )
    db.add(case)
    db.flush()
    ensure_application_tasks(
        db,
        row.citizen_session_id,
        benefit,
        application_case_id=case.id,
    )
    db.add(
        ApplicationStatusEvent(
            id=new_id("application-event"),
            application_case_id=case.id,
            status="draft",
            provenance="system_derived",
            actor_type="operator",
            actor_id="assisted-saathi",
            occurred_at=now,
            recorded_at=now,
            source_url=source_url,
            reason_code="assisted_application_created",
        )
    )
    return case


def _create_assistance_ticket(
    db: Session,
    row: AssistanceSession,
    action: AssistanceAction,
    principal: AdminPrincipal,
) -> EscalationTicket:
    if not row.citizen_session_id:
        raise HTTPException(
            status_code=409,
            detail="This assistance session has no citizen support session",
        )
    household = db.get(Household, row.household_id) if row.household_id else None
    entry = None
    if action.target_type == "department" and action.target_id:
        entry = db.get(DepartmentDirectoryEntry, action.target_id)
        if entry is None and action.action_key == "create_escalation":
            raise HTTPException(
                status_code=404,
                detail="The selected department was not found",
            )
        if entry is not None and (entry.approval_status != "approved" or not entry.is_active):
            raise HTTPException(
                status_code=409,
                detail="The selected department is not approved for routing",
            )
        if entry is not None and (
            entry.source_last_verified is None
            or _as_utc(entry.source_last_verified)
            < datetime.now(UTC) - timedelta(days=max(1, settings.department_directory_stale_days))
        ):
            raise HTTPException(
                status_code=409,
                detail="The selected department directory record is stale",
            )
    if entry is not None:
        department = entry.department_name[:160]
        location = entry.district_name[:120]
        routing_source = "approved_department_directory"
        directory_entry_id = entry.id
        source_url = entry.source_url
        verified_at = entry.source_last_verified
    else:
        route = resolve_escalation_route(
            state_code=household.state_code if household else "",
            domain=None,
            slots={"location": household.district if household else ""},
            db=db,
        )
        department = route.department
        location = route.routing_location
        routing_source = route.routing_source
        directory_entry_id = route.directory_entry_id
        source_url = route.source_url
        verified_at = route.verified_at
    now = datetime.now(UTC)
    ticket = EscalationTicket(
        id=ticket_id(),
        session_id=row.citizen_session_id,
        reason=f"assisted_saathi:{row.purpose}",
        caller_context={
            "assistance_session_id": row.id,
            "assistance_action_id": action.id,
            "household_member": bool(row.household_member_id),
        },
        transcript_excerpt="",
        sla_due_at=now + timedelta(hours=max(1, settings.escalation_sla_hours)),
        department=department,
        routing_location=location,
        routing_source=routing_source,
        routing_directory_entry_id=directory_entry_id,
        routing_source_url=source_url,
        routing_verified_at=verified_at,
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    db.add(
        make_audit_event(
            principal=principal,
            action="assistance.downstream.escalation.create",
            target_type="escalation_ticket",
            target_id=ticket.id,
            reason="Created from a citizen-confirmed Saathi action",
            safe_before={"exists": False},
            safe_after={
                "exists": True,
                "routing_source": ticket.routing_source,
                "directory_entry": bool(ticket.routing_directory_entry_id),
            },
        )
    )
    return ticket


def _get_action(db: Session, assistance_id: str, action_id: str) -> AssistanceAction:
    action = db.get(AssistanceAction, action_id)
    if action is None or action.assistance_session_id != assistance_id:
        raise HTTPException(status_code=404, detail="No such assistance action")
    return action


def _invitation_out(row: AssistanceSession, *, token: str) -> AssistanceInvitationOut:
    return AssistanceInvitationOut(
        id=row.id,
        invitation_token=token,
        status=row.status,
        purpose=row.purpose,
        approved_data_categories=list(row.approved_data_categories),
        allowed_action_keys=list(row.allowed_action_keys),
        locale=row.locale,
        notice_version=row.projection_version,
        expires_at=row.expires_at,
    )


def _session_out(row: AssistanceSession, *, include_projection: bool) -> AssistanceSessionOut:
    projection = {}
    if include_projection and row.status == "active":
        projection = {
            "projection_version": row.projection_version,
            "purpose": row.purpose,
            "data_categories": list(row.approved_data_categories),
            "allowed_action_keys": list(row.allowed_action_keys),
            "subject": {
                "type": "household_member" if row.household_member_id else "citizen_account",
                "safe_member_id": row.household_member_id or "",
            },
            "live_data_required": True,
        }
    return AssistanceSessionOut(
        id=row.id,
        purpose=row.purpose,
        status=row.status,
        approved_data_categories=list(row.approved_data_categories),
        allowed_action_keys=list(row.allowed_action_keys),
        locale=row.locale,
        helper_actor_id=row.helper_actor_id,
        helper_org_id=row.helper_org_id,
        expires_at=row.expires_at,
        last_activity_at=row.last_activity_at,
        created_at=row.created_at,
        consented_at=row.consented_at,
        ended_at=row.ended_at,
        revision=row.revision,
        projection=projection,
    )


def _action_out(action: AssistanceAction) -> AssistanceActionOut:
    return AssistanceActionOut(
        id=action.id,
        action_key=action.action_key,
        target_type=action.target_type,
        target_id=action.target_id,
        stage=action.stage,
        preview_code=str(action.safe_preview.get("preview_code", "")),
        effect_code=str(action.safe_preview.get("effect_code", "")),
        effect_reference_masked=str(action.safe_preview.get("effect_reference_masked", "")),
        effect_record_id=str(action.safe_preview.get("effect_record_id", "")),
        confirmation_mode=action.confirmation_mode,
        error_code=action.error_code,
        created_at=action.created_at,
        updated_at=action.updated_at,
    )


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _safe_hash(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
