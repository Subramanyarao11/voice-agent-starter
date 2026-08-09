"""Account-owned household and profile-fact APIs.

This first slice deliberately stops at governed household setup, member
management, and one-fact writes. It does not run proactive matching yet. That
separation keeps a durable profile useful without implying that an unreviewed
or stale fact is an eligibility decision.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from sahaayak_api.citizen_auth import (
    CitizenPrincipal,
    get_or_create_citizen_account,
    require_citizen,
)
from sahaayak_common import (
    CitizenAccount,
    Household,
    HouseholdConsentEvent,
    HouseholdMember,
    ProfileDataEncryptionUnavailable,
    ProfileFact,
    ProfileFactDefinition,
    ProfileFactRevision,
    State,
    encrypt_profile_value,
    get_session,
    mask_profile_value,
    new_id,
    normalize_profile_value,
    profile_value_hash,
    settings,
)

router = APIRouter(prefix="/api", tags=["citizen households"])

CONSENT_NOTICE_VERSION = "household-radar-2026-08-09.v1"
_FACT_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,79}$")
_PURPOSES = {
    "benefit_matching",
    "application_preparation",
    "reminders",
    "routing",
}
_RELATIONSHIPS = {
    "self",
    "child",
    "spouse_partner",
    "parent",
    "sibling",
    "dependant",
    "other",
}
_AGE_CLASSES = {"child", "youth", "adult", "senior", "unknown"}


class HouseholdCreate(BaseModel):
    label: str = Field(default="My household", min_length=1, max_length=120)
    state_code: str | None = Field(default=None, min_length=2, max_length=16)
    district: str | None = Field(default=None, max_length=120)
    pincode: str | None = Field(default=None, min_length=6, max_length=6)
    include_self: bool = True
    consent_persistence: bool = False
    consent_personalization: bool = False


class HouseholdUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    state_code: str | None = Field(default=None, min_length=2, max_length=16)
    district: str | None = Field(default=None, max_length=120)
    pincode: str | None = Field(default=None, min_length=6, max_length=6)
    expected_revision: int | None = Field(default=None, ge=1)


class HouseholdOut(BaseModel):
    id: str
    label: str
    state_code: str | None
    district: str
    pincode: str
    status: str
    revision: int
    matching_policy_version: str
    member_count: int
    created_at: datetime
    updated_at: datetime


class CitizenMeOut(BaseModel):
    id: str
    identity_provider: str
    preferred_language_code: str
    timezone: str
    status: str
    household_ids: list[str]
    created_at: datetime
    last_login_at: datetime


class MemberCreate(BaseModel):
    alias: str = Field(default="Member", min_length=1, max_length=120)
    relationship_category: str = "other"
    age_class: str = "unknown"
    authority_confirmed: bool = False
    consent_member_management: bool = False


class MemberUpdate(BaseModel):
    alias: str | None = Field(default=None, min_length=1, max_length=120)
    relationship_category: str | None = None
    age_class: str | None = None
    authority_confirmed: bool | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class HouseholdMemberOut(BaseModel):
    id: str
    alias: str
    safe_ordinal: str
    relationship_category: str
    is_account_owner_subject: bool
    age_class: str
    authority_status: str
    status: str
    revision: int
    created_at: datetime
    updated_at: datetime


class FactDefinitionOut(BaseModel):
    fact_key: str
    version: int
    scope: str
    data_type: str
    allowed_values: list[str]
    allowed_purposes: list[str]
    sensitivity: str
    inheritance_allowed: bool
    reconfirmation_days: int | None
    question: dict[str, str]
    help_text: dict[str, str]
    matcher_slot: str | None


class ProfileFactOut(FactDefinitionOut):
    state: Literal["missing", "current", "stale"]
    masked_value: str
    value_source: str
    purposes: list[str]
    confirmed_at: datetime | None
    reconfirm_after: datetime | None
    expires_at: datetime | None
    revision: int | None


class ProfileFactWrite(BaseModel):
    value: str = Field(min_length=1, max_length=2_000)
    purposes: list[str] = Field(min_length=1, max_length=4)
    confirm_purpose: bool = False
    expected_revision: int | None = Field(default=None, ge=1)


class ProfileFactConfirm(BaseModel):
    expected_revision: int | None = Field(default=None, ge=1)


class ProfileFactRevisionOut(BaseModel):
    revision: int
    action: str
    reason: str
    before_masked_value: str
    after_masked_value: str
    definition_version: int
    created_at: datetime


@router.get("/citizen/me", response_model=CitizenMeOut)
def citizen_me(
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> CitizenMeOut:
    account = _account(db, principal)
    households = db.exec(
        select(Household).where(
            Household.owner_account_id == account.id,
            Household.status != "deleted",
        )
    ).all()
    db.commit()
    return CitizenMeOut(
        id=account.id,
        identity_provider=account.identity_provider,
        preferred_language_code=account.preferred_language_code,
        timezone=account.timezone,
        status=account.status,
        household_ids=[row.id for row in households],
        created_at=account.created_at,
        last_login_at=account.last_login_at,
    )


@router.post("/households", response_model=HouseholdOut, status_code=status.HTTP_201_CREATED)
def create_household(
    payload: HouseholdCreate,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> HouseholdOut:
    if not payload.consent_persistence:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit household persistence consent is required",
        )
    account = _account(db, principal)
    active_households = db.exec(
        select(Household).where(
            Household.owner_account_id == account.id,
            Household.status == "active",
        )
    ).all()
    if active_households:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This demo account already has an active household",
        )
    state_code = _normalize_state(db, payload.state_code)
    district = _normalize_optional_text(payload.district, max_length=120)
    pincode = _normalize_pincode(payload.pincode)
    label = normalize_profile_value(payload.label)[:120]
    try:
        row = Household(
            id=new_id("household"),
            owner_account_id=account.id,
            label_ciphertext=encrypt_profile_value(label),
            label_masked=mask_profile_value(label),
            state_code=state_code,
            district=district or "",
            pincode_ciphertext=encrypt_profile_value(pincode) if pincode else None,
            pincode_masked=_mask_pincode(pincode),
            pincode_prefix=pincode[:3] if pincode else None,
            retention_expires_at=datetime.now(UTC)
            + timedelta(days=max(1, settings.citizen_household_retention_days)),
        )
    except (ProfileDataEncryptionUnavailable, ValueError) as exc:
        raise _profile_storage_error() from exc
    db.add(row)
    _record_consent(
        db,
        account=account,
        household=row,
        purpose="household_persistence",
        action="granted",
        principal=principal,
    )
    if payload.consent_personalization:
        _record_consent(
            db,
            account=account,
            household=row,
            purpose="benefit_matching",
            action="granted",
            principal=principal,
        )
    if payload.include_self:
        try:
            _create_self_member(db, row)
        except (ProfileDataEncryptionUnavailable, ValueError) as exc:
            raise _profile_storage_error() from exc
    db.commit()
    db.refresh(row)
    return _household_out(db, row)


@router.get("/households", response_model=list[HouseholdOut])
def list_households(
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> list[HouseholdOut]:
    account = _account(db, principal)
    rows = db.exec(
        select(Household)
        .where(
            Household.owner_account_id == account.id,
            Household.status != "deleted",
        )
        .order_by(Household.created_at.desc())
    ).all()
    db.commit()
    return [_household_out(db, row) for row in rows]


@router.get("/households/{household_id}", response_model=HouseholdOut)
def get_household(
    household_id: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> HouseholdOut:
    account = _account(db, principal)
    row = _owned_household(db, household_id, account.id)
    db.commit()
    return _household_out(db, row)


@router.patch("/households/{household_id}", response_model=HouseholdOut)
def update_household(
    household_id: str,
    payload: HouseholdUpdate,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> HouseholdOut:
    account = _account(db, principal)
    row = _owned_household(db, household_id, account.id)
    _check_revision(payload.expected_revision, row.revision, "household")
    if payload.label is not None:
        label = normalize_profile_value(payload.label)[:120]
        try:
            row.label_ciphertext = encrypt_profile_value(label)
        except (ProfileDataEncryptionUnavailable, ValueError) as exc:
            raise _profile_storage_error() from exc
        row.label_masked = mask_profile_value(label)
    if payload.state_code is not None:
        row.state_code = _normalize_state(db, payload.state_code)
    if payload.district is not None:
        row.district = _normalize_optional_text(payload.district, max_length=120) or ""
    if payload.pincode is not None:
        pincode = _normalize_pincode(payload.pincode)
        try:
            row.pincode_ciphertext = encrypt_profile_value(pincode) if pincode else None
        except (ProfileDataEncryptionUnavailable, ValueError) as exc:
            raise _profile_storage_error() from exc
        row.pincode_masked = _mask_pincode(pincode)
        row.pincode_prefix = pincode[:3] if pincode else None
    row.revision += 1
    row.updated_at = datetime.now(UTC)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _household_out(db, row)


@router.delete("/households/{household_id}", response_model=HouseholdOut)
def request_household_deletion(
    household_id: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> HouseholdOut:
    account = _account(db, principal)
    row = _owned_household(db, household_id, account.id)
    row.status = "pending_deletion"
    row.revision += 1
    row.updated_at = datetime.now(UTC)
    _record_consent(
        db,
        account=account,
        household=row,
        purpose="household_persistence",
        action="withdrawn",
        principal=principal,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _household_out(db, row)


@router.post(
    "/households/{household_id}/members",
    response_model=HouseholdMemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    household_id: str,
    payload: MemberCreate,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> HouseholdMemberOut:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    _validate_member_payload(payload.relationship_category, payload.age_class)
    if not payload.consent_member_management:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit member-management consent is required",
        )
    if payload.relationship_category != "self" and not payload.authority_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirm that you are authorized to manage this member profile",
        )
    if (
        payload.relationship_category in {"child", "dependant"}
        or payload.age_class == "child"
    ) and not settings.citizen_household_dependants_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Child profiles require the reviewed guardian policy to be enabled",
        )
    active_members = db.exec(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household.id,
            HouseholdMember.status == "active",
        )
    ).all()
    if len(active_members) >= max(1, settings.citizen_household_max_members):
        raise HTTPException(status_code=409, detail="Household member limit reached")
    if payload.relationship_category == "self" and any(
        member.is_account_owner_subject for member in active_members
    ):
        raise HTTPException(status_code=409, detail="This household already has a self member")
    ordinal = f"member_{len(active_members) + 1}"
    alias = normalize_profile_value(payload.alias)[:120]
    try:
        row = HouseholdMember(
            id=new_id("member"),
            household_id=household.id,
            alias_ciphertext=encrypt_profile_value(alias),
            alias_masked=mask_profile_value(alias),
            safe_ordinal=ordinal,
            relationship_category=payload.relationship_category,
            is_account_owner_subject=payload.relationship_category == "self",
            age_class=payload.age_class,
            authority_status=(
                "confirmed"
                if payload.authority_confirmed
                else "not_applicable"
            ),
            authority_confirmed_at=(datetime.now(UTC) if payload.authority_confirmed else None),
        )
    except (ProfileDataEncryptionUnavailable, ValueError) as exc:
        raise _profile_storage_error() from exc
    db.add(row)
    _record_consent(
        db,
        account=account,
        household=household,
        member=row,
        purpose="member_management",
        action="granted",
        principal=principal,
    )
    db.commit()
    db.refresh(row)
    return _member_out(row)


@router.get("/households/{household_id}/members", response_model=list[HouseholdMemberOut])
def list_members(
    household_id: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> list[HouseholdMemberOut]:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    rows = db.exec(
        select(HouseholdMember)
        .where(
            HouseholdMember.household_id == household.id,
            HouseholdMember.status == "active",
        )
        .order_by(HouseholdMember.safe_ordinal)
    ).all()
    db.commit()
    return [_member_out(row) for row in rows]


@router.get("/households/{household_id}/members/{member_id}", response_model=HouseholdMemberOut)
def get_member(
    household_id: str,
    member_id: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> HouseholdMemberOut:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    row = _owned_member(db, household.id, member_id)
    db.commit()
    return _member_out(row)


@router.patch("/households/{household_id}/members/{member_id}", response_model=HouseholdMemberOut)
def update_member(
    household_id: str,
    member_id: str,
    payload: MemberUpdate,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> HouseholdMemberOut:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    row = _owned_member(db, household.id, member_id)
    _check_revision(payload.expected_revision, row.revision, "member")
    relationship = payload.relationship_category or row.relationship_category
    age_class = payload.age_class or row.age_class
    _validate_member_payload(relationship, age_class)
    if relationship in {"child", "dependant"} or age_class == "child":
        if not settings.citizen_household_dependants_enabled:
            raise HTTPException(
                status_code=409,
                detail="Child profiles require the reviewed guardian policy to be enabled",
            )
    if relationship != "self" and row.authority_status != "confirmed":
        if not payload.authority_confirmed:
            raise HTTPException(
                status_code=400,
                detail="Confirm authority before changing this member profile",
            )
    if relationship == "self" and not row.is_account_owner_subject:
        other_self = db.exec(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household.id,
                HouseholdMember.is_account_owner_subject.is_(True),
                HouseholdMember.status == "active",
            )
        ).first()
        if other_self is not None:
            raise HTTPException(status_code=409, detail="This household already has a self member")
    if payload.alias is not None:
        alias = normalize_profile_value(payload.alias)[:120]
        try:
            row.alias_ciphertext = encrypt_profile_value(alias)
        except (ProfileDataEncryptionUnavailable, ValueError) as exc:
            raise _profile_storage_error() from exc
        row.alias_masked = mask_profile_value(alias)
    if payload.relationship_category is not None:
        row.relationship_category = payload.relationship_category
        row.is_account_owner_subject = payload.relationship_category == "self"
    if payload.age_class is not None:
        row.age_class = payload.age_class
    if payload.authority_confirmed:
        row.authority_status = "confirmed"
        row.authority_confirmed_at = datetime.now(UTC)
    row.revision += 1
    row.updated_at = datetime.now(UTC)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _member_out(row)


@router.delete("/households/{household_id}/members/{member_id}", response_model=HouseholdMemberOut)
def delete_member(
    household_id: str,
    member_id: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> HouseholdMemberOut:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    row = _owned_member(db, household.id, member_id)
    if row.is_account_owner_subject:
        raise HTTPException(status_code=409, detail="The account owner member cannot be removed")
    row.status = "deleted"
    row.alias_ciphertext = None
    row.alias_masked = "Removed member"
    row.revision += 1
    row.updated_at = datetime.now(UTC)
    for fact in db.exec(
        select(ProfileFact).where(
            ProfileFact.household_member_id == row.id,
            ProfileFact.status == "current",
        )
    ).all():
        _delete_fact_row(db, fact, actor_id=principal.subject_hash, reason="member_deleted")
    _record_consent(
        db,
        account=account,
        household=household,
        member=row,
        purpose="member_management",
        action="withdrawn",
        principal=principal,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _member_out(row)


@router.get("/households/{household_id}/facts", response_model=list[ProfileFactOut])
def list_household_facts(
    household_id: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> list[ProfileFactOut]:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    return _list_facts(db, household, member_id=None)


@router.get(
    "/households/{household_id}/members/{member_id}/facts",
    response_model=list[ProfileFactOut],
)
def list_member_facts(
    household_id: str,
    member_id: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> list[ProfileFactOut]:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    _owned_member(db, household.id, member_id)
    return _list_facts(db, household, member_id=member_id)


@router.put("/households/{household_id}/facts/{fact_key}", response_model=ProfileFactOut)
def write_household_fact(
    household_id: str,
    fact_key: str,
    payload: ProfileFactWrite,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> ProfileFactOut:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    return _write_fact(db, account, principal, household, None, fact_key, payload)


@router.put(
    "/households/{household_id}/members/{member_id}/facts/{fact_key}",
    response_model=ProfileFactOut,
)
def write_member_fact(
    household_id: str,
    member_id: str,
    fact_key: str,
    payload: ProfileFactWrite,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> ProfileFactOut:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    _owned_member(db, household.id, member_id)
    return _write_fact(db, account, principal, household, member_id, fact_key, payload)


@router.post(
    "/households/{household_id}/facts/{fact_key}/confirm",
    response_model=ProfileFactOut,
)
def confirm_household_fact(
    household_id: str,
    fact_key: str,
    payload: ProfileFactConfirm,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> ProfileFactOut:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    return _confirm_fact(db, account, principal, household, None, fact_key, payload)


@router.post(
    "/households/{household_id}/members/{member_id}/facts/{fact_key}/confirm",
    response_model=ProfileFactOut,
)
def confirm_member_fact(
    household_id: str,
    member_id: str,
    fact_key: str,
    payload: ProfileFactConfirm,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> ProfileFactOut:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    _owned_member(db, household.id, member_id)
    return _confirm_fact(db, account, principal, household, member_id, fact_key, payload)


@router.delete(
    "/households/{household_id}/facts/{fact_key}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_household_fact(
    household_id: str,
    fact_key: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> Response:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    _remove_fact(db, account, principal, household, None, fact_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/households/{household_id}/members/{member_id}/facts/{fact_key}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_member_fact(
    household_id: str,
    member_id: str,
    fact_key: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> Response:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    _owned_member(db, household.id, member_id)
    _remove_fact(db, account, principal, household, member_id, fact_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/households/{household_id}/facts/{fact_key}/history",
    response_model=list[ProfileFactRevisionOut],
)
def household_fact_history(
    household_id: str,
    fact_key: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> list[ProfileFactRevisionOut]:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    fact = _find_fact_any(db, household.id, None, fact_key)
    return _history(db, fact)


@router.get(
    "/households/{household_id}/members/{member_id}/facts/{fact_key}/history",
    response_model=list[ProfileFactRevisionOut],
)
def member_fact_history(
    household_id: str,
    member_id: str,
    fact_key: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> list[ProfileFactRevisionOut]:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    _owned_member(db, household.id, member_id)
    fact = _find_fact_any(db, household.id, member_id, fact_key)
    return _history(db, fact)


@router.get("/citizen/fact-definitions", response_model=list[FactDefinitionOut])
def list_fact_definitions(
    db: Session = Depends(get_session),
    _principal: CitizenPrincipal = Depends(require_citizen),
) -> list[FactDefinitionOut]:
    rows = db.exec(
        select(ProfileFactDefinition)
        .where(ProfileFactDefinition.review_status == "approved")
        .order_by(ProfileFactDefinition.scope, ProfileFactDefinition.fact_key)
    ).all()
    return [_definition_out(row) for row in rows]


def _account(db: Session, principal: CitizenPrincipal) -> CitizenAccount:
    account = get_or_create_citizen_account(db, principal)
    account.last_login_at = datetime.now(UTC)
    db.add(account)
    db.flush()
    return account


def _owned_household(db: Session, household_id: str, account_id: str) -> Household:
    row = db.exec(
        select(Household).where(
            Household.id == household_id,
            Household.owner_account_id == account_id,
            Household.status != "deleted",
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Household not found")
    return row


def _owned_member(db: Session, household_id: str, member_id: str) -> HouseholdMember:
    row = db.exec(
        select(HouseholdMember).where(
            HouseholdMember.id == member_id,
            HouseholdMember.household_id == household_id,
            HouseholdMember.status == "active",
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Household member not found")
    return row


def _household_out(db: Session, row: Household) -> HouseholdOut:
    count = len(
        db.exec(
            select(HouseholdMember).where(
                HouseholdMember.household_id == row.id,
                HouseholdMember.status == "active",
            )
        ).all()
    )
    return HouseholdOut(
        id=row.id,
        label=row.label_masked,
        state_code=row.state_code,
        district=row.district,
        pincode=row.pincode_masked,
        status=row.status,
        revision=row.revision,
        matching_policy_version=row.matching_policy_version,
        member_count=count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _member_out(row: HouseholdMember) -> HouseholdMemberOut:
    return HouseholdMemberOut(
        id=row.id,
        alias=row.alias_masked,
        safe_ordinal=row.safe_ordinal,
        relationship_category=row.relationship_category,
        is_account_owner_subject=row.is_account_owner_subject,
        age_class=row.age_class,
        authority_status=row.authority_status,
        status=row.status,
        revision=row.revision,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _definition_out(row: ProfileFactDefinition) -> FactDefinitionOut:
    return FactDefinitionOut(
        fact_key=row.fact_key,
        version=row.version,
        scope=row.scope,
        data_type=row.data_type,
        allowed_values=row.allowed_values,
        allowed_purposes=row.allowed_purposes,
        sensitivity=row.sensitivity,
        inheritance_allowed=row.inheritance_allowed,
        reconfirmation_days=row.reconfirmation_days,
        question=row.question,
        help_text=row.help_text,
        matcher_slot=row.matcher_slot,
    )


def _list_facts(
    db: Session,
    household: Household,
    *,
    member_id: str | None,
) -> list[ProfileFactOut]:
    scope = "household" if member_id is None else "member"
    definitions = db.exec(
        select(ProfileFactDefinition)
        .where(
            ProfileFactDefinition.scope == scope,
            ProfileFactDefinition.review_status == "approved",
        )
        .order_by(ProfileFactDefinition.fact_key, ProfileFactDefinition.version.desc())
    ).all()
    latest: dict[str, ProfileFactDefinition] = {}
    for definition in definitions:
        latest.setdefault(definition.fact_key, definition)
    return [
        _fact_out(
            definition,
            _find_fact_optional(db, household.id, member_id, definition.fact_key),
        )
        for definition in latest.values()
    ]


def _fact_out(
    definition: ProfileFactDefinition,
    fact: ProfileFact | None,
) -> ProfileFactOut:
    now = datetime.now(UTC)
    stale = bool(
        fact is not None
        and (
            _past(fact.reconfirm_after, now)
            or _past(fact.expires_at, now)
        )
    )
    return ProfileFactOut(
        **_definition_out(definition).model_dump(),
        state="stale" if stale else "current" if fact is not None else "missing",
        masked_value=fact.masked_value if fact is not None and not stale else "",
        value_source=fact.value_source if fact is not None else "",
        purposes=fact.purposes if fact is not None else [],
        confirmed_at=fact.confirmed_at if fact is not None else None,
        reconfirm_after=fact.reconfirm_after if fact is not None else None,
        expires_at=fact.expires_at if fact is not None else None,
        revision=fact.revision if fact is not None else None,
    )


def _write_fact(
    db: Session,
    account: CitizenAccount,
    principal: CitizenPrincipal,
    household: Household,
    member_id: str | None,
    fact_key: str,
    payload: ProfileFactWrite,
) -> ProfileFactOut:
    definition = _definition(db, fact_key, scope="household" if member_id is None else "member")
    if not payload.confirm_purpose:
        raise HTTPException(
            status_code=400,
            detail="Confirm why this fact is being stored before saving it",
        )
    purposes = sorted(set(purpose.strip() for purpose in payload.purposes if purpose.strip()))
    if not purposes or not set(purposes).issubset(set(definition.allowed_purposes)):
        raise HTTPException(
            status_code=422,
            detail="This fact is not allowed for one or more requested purposes",
        )
    value = _validate_fact_value(definition, payload.value)
    existing = _find_fact_optional(db, household.id, member_id, fact_key)
    if existing is None:
        existing = _find_fact_any_optional(db, household.id, member_id, fact_key)
    if existing is not None:
        _check_revision(payload.expected_revision, existing.revision, "profile fact")
    elif payload.expected_revision is not None:
        raise HTTPException(status_code=409, detail="This profile fact does not exist")
    try:
        ciphertext = encrypt_profile_value(value)
        value_hash = profile_value_hash(value)
    except (ProfileDataEncryptionUnavailable, ValueError) as exc:
        raise _profile_storage_error() from exc
    now = datetime.now(UTC)
    reconfirm_after = (
        now + timedelta(days=definition.reconfirmation_days)
        if definition.reconfirmation_days
        else None
    )
    if existing is None:
        existing = ProfileFact(
            id=new_id("fact"),
            household_id=household.id,
            household_member_id=member_id,
            fact_key=fact_key,
            definition_version=definition.version,
            value_ciphertext=ciphertext,
            value_hash=value_hash,
            masked_value=mask_profile_value(value),
            value_source="citizen_confirmed",
            purposes=purposes,
            confirmed_by=principal.subject_hash,
            confirmed_at=now,
            reconfirm_after=reconfirm_after,
        )
        action = "created"
        before_masked = ""
        revision = 1
    else:
        before_masked = existing.masked_value
        action = (
            "restored"
            if existing.status == "deleted"
            else "confirmed"
            if existing.value_hash == value_hash
            else "updated"
        )
        existing.definition_version = definition.version
        existing.value_ciphertext = ciphertext
        existing.value_hash = value_hash
        existing.masked_value = mask_profile_value(value)
        existing.value_source = "citizen_confirmed"
        existing.purposes = purposes
        existing.confirmed_by = principal.subject_hash
        existing.confirmed_at = now
        existing.reconfirm_after = reconfirm_after
        existing.expires_at = None
        existing.status = "current"
        existing.revision += 1
        existing.updated_at = now
        revision = existing.revision
    db.add(existing)
    db.add(
        ProfileFactRevision(
            id=new_id("factrev"),
            profile_fact_id=existing.id,
            revision=revision,
            action=action,
            actor_id=principal.subject_hash,
            reason="citizen_confirmed_profile_fact",
            before_masked_value=before_masked,
            after_masked_value=existing.masked_value,
            value_hash=value_hash,
            definition_version=definition.version,
        )
    )
    for purpose in purposes:
        _record_consent(
            db,
            account=account,
            household=household,
            member_id=member_id,
            purpose=purpose,
            action="granted",
            principal=principal,
            safe_context={"fact_key": fact_key, "definition_version": definition.version},
        )
    db.commit()
    db.refresh(existing)
    return _fact_out(definition, existing)


def _confirm_fact(
    db: Session,
    account: CitizenAccount,
    principal: CitizenPrincipal,
    household: Household,
    member_id: str | None,
    fact_key: str,
    payload: ProfileFactConfirm,
) -> ProfileFactOut:
    definition = _definition(db, fact_key, scope="household" if member_id is None else "member")
    fact = _find_fact(db, household.id, member_id, fact_key)
    _check_revision(payload.expected_revision, fact.revision, "profile fact")
    now = datetime.now(UTC)
    fact.confirmed_at = now
    fact.confirmed_by = principal.subject_hash
    fact.reconfirm_after = (
        now + timedelta(days=definition.reconfirmation_days)
        if definition.reconfirmation_days
        else None
    )
    fact.expires_at = None
    fact.status = "current"
    fact.revision += 1
    fact.updated_at = now
    db.add(fact)
    db.add(
        ProfileFactRevision(
            id=new_id("factrev"),
            profile_fact_id=fact.id,
            revision=fact.revision,
            action="confirmed",
            actor_id=principal.subject_hash,
            reason="citizen_reconfirmed_profile_fact",
            before_masked_value=fact.masked_value,
            after_masked_value=fact.masked_value,
            value_hash=fact.value_hash,
            definition_version=definition.version,
        )
    )
    db.commit()
    db.refresh(fact)
    return _fact_out(definition, fact)


def _remove_fact(
    db: Session,
    account: CitizenAccount,
    principal: CitizenPrincipal,
    household: Household,
    member_id: str | None,
    fact_key: str,
) -> None:
    definition = _definition(db, fact_key, scope="household" if member_id is None else "member")
    fact = _find_fact(db, household.id, member_id, fact_key)
    _delete_fact_row(db, fact, actor_id=principal.subject_hash, reason="citizen_deleted")
    for purpose in fact.purposes:
        _record_consent(
            db,
            account=account,
            household=household,
            member_id=member_id,
            purpose=purpose,
            action="withdrawn",
            principal=principal,
            safe_context={"fact_key": definition.fact_key},
        )
    db.commit()


def _delete_fact_row(db: Session, fact: ProfileFact, *, actor_id: str, reason: str) -> None:
    previous = fact.masked_value
    fact.value_ciphertext = ""
    fact.value_hash = ""
    fact.masked_value = ""
    fact.status = "deleted"
    fact.revision += 1
    fact.updated_at = datetime.now(UTC)
    db.add(fact)
    db.add(
        ProfileFactRevision(
            id=new_id("factrev"),
            profile_fact_id=fact.id,
            revision=fact.revision,
            action="deleted",
            actor_id=actor_id,
            reason=reason,
            before_masked_value=previous,
            after_masked_value="",
            value_hash="",
            definition_version=fact.definition_version,
        )
    )


def _history(db: Session, fact: ProfileFact) -> list[ProfileFactRevisionOut]:
    rows = db.exec(
        select(ProfileFactRevision)
        .where(ProfileFactRevision.profile_fact_id == fact.id)
        .order_by(ProfileFactRevision.revision)
    ).all()
    return [
        ProfileFactRevisionOut(
            revision=row.revision,
            action=row.action,
            reason=row.reason,
            before_masked_value=row.before_masked_value,
            after_masked_value=row.after_masked_value,
            definition_version=row.definition_version,
            created_at=row.created_at,
        )
        for row in rows
    ]


def _definition(db: Session, fact_key: str, *, scope: str) -> ProfileFactDefinition:
    if not _FACT_KEY_RE.fullmatch(fact_key):
        raise HTTPException(status_code=422, detail="Invalid profile fact key")
    row = db.exec(
        select(ProfileFactDefinition)
        .where(
            ProfileFactDefinition.fact_key == fact_key,
            ProfileFactDefinition.scope == scope,
            ProfileFactDefinition.review_status == "approved",
        )
        .order_by(ProfileFactDefinition.version.desc())
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Profile fact is not enabled")
    return row


def _find_fact_optional(
    db: Session,
    household_id: str,
    member_id: str | None,
    fact_key: str,
) -> ProfileFact | None:
    query = select(ProfileFact).where(
        ProfileFact.household_id == household_id,
        ProfileFact.fact_key == fact_key,
        ProfileFact.status == "current",
    )
    if member_id is None:
        query = query.where(ProfileFact.household_member_id.is_(None))
    else:
        query = query.where(ProfileFact.household_member_id == member_id)
    return db.exec(query).first()


def _find_fact(db: Session, household_id: str, member_id: str | None, fact_key: str) -> ProfileFact:
    row = _find_fact_optional(db, household_id, member_id, fact_key)
    if row is None:
        raise HTTPException(status_code=404, detail="Profile fact not found")
    return row


def _find_fact_any(
    db: Session,
    household_id: str,
    member_id: str | None,
    fact_key: str,
) -> ProfileFact:
    query = select(ProfileFact).where(
        ProfileFact.household_id == household_id,
        ProfileFact.fact_key == fact_key,
    )
    if member_id is None:
        query = query.where(ProfileFact.household_member_id.is_(None))
    else:
        query = query.where(ProfileFact.household_member_id == member_id)
    row = db.exec(query.order_by(ProfileFact.updated_at.desc())).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Profile fact not found")
    return row


def _find_fact_any_optional(
    db: Session,
    household_id: str,
    member_id: str | None,
    fact_key: str,
) -> ProfileFact | None:
    query = select(ProfileFact).where(
        ProfileFact.household_id == household_id,
        ProfileFact.fact_key == fact_key,
    )
    if member_id is None:
        query = query.where(ProfileFact.household_member_id.is_(None))
    else:
        query = query.where(ProfileFact.household_member_id == member_id)
    return db.exec(query.order_by(ProfileFact.updated_at.desc())).first()


def _record_consent(
    db: Session,
    *,
    account: CitizenAccount,
    household: Household,
    principal: CitizenPrincipal,
    purpose: str,
    action: str,
    member: HouseholdMember | None = None,
    member_id: str | None = None,
    safe_context: dict | None = None,
) -> None:
    db.add(
        HouseholdConsentEvent(
            id=new_id("hconsent"),
            citizen_account_id=account.id,
            household_id=household.id,
            household_member_id=member.id if member is not None else member_id,
            purpose=purpose,
            action=action,
            notice_version=CONSENT_NOTICE_VERSION,
            locale=account.preferred_language_code,
            actor_id=principal.subject_hash,
            safe_context=safe_context or {},
        )
    )


def _create_self_member(
    db: Session,
    household: Household,
) -> HouseholdMember:
    alias = "Me"
    row = HouseholdMember(
        id=new_id("member"),
        household_id=household.id,
        alias_ciphertext=encrypt_profile_value(alias),
        alias_masked=mask_profile_value(alias),
        safe_ordinal="member_1",
        relationship_category="self",
        is_account_owner_subject=True,
        age_class="unknown",
        authority_status="not_applicable",
    )
    db.add(row)
    return row


def _normalize_state(db: Session, state_code: str | None) -> str | None:
    if state_code is None:
        return None
    normalized = state_code.strip().upper()
    row = db.get(State, normalized)
    if row is None:
        raise HTTPException(status_code=422, detail="state_code must reference a configured state")
    return row.code


def _normalize_optional_text(value: str | None, *, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = normalize_profile_value(value)
    if len(normalized) > max_length:
        raise HTTPException(status_code=422, detail="Text value is too long")
    return normalized


def _normalize_pincode(value: str | None) -> str:
    if value is None or not value.strip():
        return ""
    normalized = value.strip()
    if not normalized.isdigit() or len(normalized) != 6:
        raise HTTPException(status_code=422, detail="pincode must contain six digits")
    return normalized


def _mask_pincode(value: str) -> str:
    return f"••••{value[-2:]}" if value else ""


def _validate_member_payload(relationship: str, age_class: str) -> None:
    if relationship not in _RELATIONSHIPS:
        raise HTTPException(status_code=422, detail="Unsupported relationship category")
    if age_class not in _AGE_CLASSES:
        raise HTTPException(status_code=422, detail="Unsupported age class")
    if relationship == "self" and age_class == "child":
        raise HTTPException(status_code=422, detail="The account owner cannot use child age class")


def _validate_fact_value(definition: ProfileFactDefinition, raw_value: str) -> str:
    try:
        value = normalize_profile_value(raw_value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Profile fact value is invalid") from exc
    if definition.data_type == "select" and value not in definition.allowed_values:
        raise HTTPException(status_code=422, detail="Profile fact value is not an allowed option")
    if definition.data_type == "integer":
        try:
            parsed = int(value)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="Profile fact must be a whole number",
            ) from exc
        minimum = definition.validation.get("min")
        maximum = definition.validation.get("max")
        if (minimum is not None and parsed < minimum) or (maximum is not None and parsed > maximum):
            raise HTTPException(status_code=422, detail="Profile fact is outside the allowed range")
        value = str(parsed)
    minimum_length = definition.validation.get("min_length")
    maximum_length = definition.validation.get("max_length")
    if minimum_length is not None and len(value) < minimum_length:
        raise HTTPException(status_code=422, detail="Profile fact is too short")
    if maximum_length is not None and len(value) > maximum_length:
        raise HTTPException(status_code=422, detail="Profile fact is too long")
    pattern = definition.validation.get("pattern")
    if pattern and re.fullmatch(pattern, value) is None:
        raise HTTPException(status_code=422, detail="Profile fact has an invalid format")
    return value


def _check_revision(expected: int | None, current: int, label: str) -> None:
    if expected is not None and expected != current:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{label.capitalize()} changed; expected revision {expected}, "
                f"current revision {current}"
            ),
        )


def _past(value: datetime | None, now: datetime) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value <= now


def _profile_storage_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="Household persistence is not configured with profile encryption keys",
    )
