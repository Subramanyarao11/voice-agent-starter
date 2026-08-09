"""Consent-bound Assisted Saathi sessions.

This is the first delegated-access slice. It deliberately exposes an
invitation path for an authenticated citizen account, not a general-purpose
helper proxy. A helper can redeem a single-use capability, but the server
does not grant a projection until the citizen confirms the purpose. Action
execution is an auditable ledger operation until an explicitly integrated
downstream effect is added.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
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
from sahaayak_api.telemetry import make_audit_event
from sahaayak_common import (
    AssistanceAction,
    AssistanceConsent,
    AssistanceSession,
    Household,
    HouseholdConsentEvent,
    HouseholdMember,
    get_session,
    new_id,
    settings,
)

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
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    now = datetime.now(UTC)
    configured_ttl = max(1, settings.assistance_invitation_ttl_minutes)
    ttl_minutes = min(payload.expires_in_minutes or configured_ttl, configured_ttl)
    row = AssistanceSession(
        id=new_id("assist"),
        invitation_token_hash=_token_hash(token),
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
    _validate_action(row, payload.action_key, payload.target_type, payload.preview_code)
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
        safe_preview={"preview_code": payload.preview_code},
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
    now = datetime.now(UTC)
    action.stage = "executed"
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
            reason="Executed a citizen-confirmed action in the assistance ledger",
            safe_before={"stage": "citizen_confirmed"},
            safe_after={"stage": "executed", "effect": "ledger_only"},
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
    preview_code: str,
) -> None:
    if action_key not in row.allowed_action_keys:
        raise HTTPException(status_code=400, detail="This action is outside the session purpose")
    if target_type not in _ALLOWED_TARGET_TYPES:
        raise HTTPException(status_code=400, detail="The action target type is not allowed")
    if not preview_code or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789_.-" for character in preview_code
    ):
        raise HTTPException(status_code=400, detail="The action preview code is not safe")


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
