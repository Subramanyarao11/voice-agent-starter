"""Explicit, reviewable guest-to-citizen migration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from sahaayak_api.browser_auth import token_digest
from sahaayak_api.citizen_auth import (
    CitizenPrincipal,
    get_or_create_citizen_account,
    require_citizen,
)
from sahaayak_api.rate_limit import apply_rate_limit_headers, enforce_rate_limit
from sahaayak_api.routers.households import (
    _owned_household,
    _owned_member,
    _validate_fact_value,
)
from sahaayak_common import (
    ApplicationCase,
    ApplicationTask,
    Benefit,
    CitizenAccount,
    GuestMigration,
    HouseholdConsentEvent,
    ProfileDataEncryptionUnavailable,
    ProfileFact,
    ProfileFactDefinition,
    ProfileFactRevision,
    Reminder,
    SavedBenefit,
    UserSession,
    encrypt_profile_value,
    get_session,
    mask_profile_value,
    new_id,
    profile_value_hash,
)

router = APIRouter(prefix="/api", tags=["guest migration"])


class MigrationSelection(BaseModel):
    saved_benefit_ids: list[str] = Field(default_factory=list, max_length=50)
    task_ids: list[str] = Field(default_factory=list, max_length=100)
    reminder_ids: list[str] = Field(default_factory=list, max_length=50)
    application_case_ids: list[str] = Field(default_factory=list, max_length=25)
    profile_fact_keys: list[str] = Field(default_factory=list, max_length=12)
    target_household_id: str | None = Field(default=None, max_length=160)
    target_member_id: str | None = Field(default=None, max_length=160)
    idempotency_key: str = Field(min_length=8, max_length=160)


class MigrationCommit(BaseModel):
    confirm: bool = False


class MigrationItemOut(BaseModel):
    kind: str
    id: str
    title: str
    selected: bool
    conflict_code: str = ""


class MigrationOut(BaseModel):
    id: str
    guest_session_id: str
    status: str
    selected_object_ids: dict[str, list[str]]
    items: list[MigrationItemOut]
    conflict_report: dict[str, Any]
    source_deletion_status: str
    created_at: datetime
    updated_at: datetime


@router.post(
    "/sessions/{session_id}/migration/preview",
    response_model=MigrationOut,
    status_code=status.HTTP_201_CREATED,
)
async def preview_guest_migration(
    session_id: str,
    payload: MigrationSelection,
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> MigrationOut:
    account = get_or_create_citizen_account(db, principal)
    guest = _require_guest_proof(request, db, session_id)
    _validate_target(db, account.id, payload)
    decision = await enforce_rate_limit(
        request,
        session_id=f"{account.id}:{session_id}",
        bucket="migration",
    )
    apply_rate_limit_headers(response, decision)
    if not _has_selection(payload):
        raise HTTPException(status_code=400, detail="Select at least one guest item to migrate")
    existing = db.exec(
        select(GuestMigration).where(
            GuestMigration.citizen_account_id == account.id,
            GuestMigration.idempotency_key == payload.idempotency_key,
        )
    ).first()
    if existing is not None:
        if existing.guest_session_id != guest.id:
            raise HTTPException(
                status_code=409,
                detail="Migration idempotency key is already in use",
            )
        return _migration_out(db, existing, guest)

    selected = _selection_dict(payload)
    items, conflicts = _preview_items(db, guest, selected)
    now = datetime.now(UTC)
    row = GuestMigration(
        id=new_id("migration"),
        guest_session_id=guest.id,
        citizen_account_id=account.id,
        selected_object_ids=selected,
        status="conflict" if conflicts else "preview",
        idempotency_key=payload.idempotency_key,
        conflict_report=conflicts,
        source_deletion_status="not_started",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _migration_out(db, row, guest, items=items)


@router.get("/citizen/migrations/{migration_id}", response_model=MigrationOut)
def get_migration(
    migration_id: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> MigrationOut:
    account = get_or_create_citizen_account(db, principal)
    row = db.exec(
        select(GuestMigration).where(
            GuestMigration.id == migration_id,
            GuestMigration.citizen_account_id == account.id,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    guest = db.get(UserSession, row.guest_session_id)
    if guest is None:
        raise HTTPException(status_code=404, detail="Migration source is no longer available")
    return _migration_out(db, row, guest)


@router.post(
    "/sessions/{session_id}/migration",
    response_model=MigrationOut,
)
async def commit_guest_migration(
    session_id: str,
    payload: MigrationCommit,
    request: Request,
    response: Response,
    migration_id: str,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> MigrationOut:
    account = get_or_create_citizen_account(db, principal)
    guest = _require_guest_proof(request, db, session_id)
    decision = await enforce_rate_limit(
        request,
        session_id=f"{account.id}:{session_id}",
        bucket="migration",
    )
    apply_rate_limit_headers(response, decision)
    row = db.exec(
        select(GuestMigration).where(
            GuestMigration.id == migration_id,
            GuestMigration.guest_session_id == guest.id,
            GuestMigration.citizen_account_id == account.id,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    if row.status == "completed":
        return _migration_out(db, row, guest)
    if not payload.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirm the migration after reviewing the preview",
        )
    if row.conflict_report:
        raise HTTPException(status_code=409, detail="Resolve migration conflicts before confirming")
    selected = row.selected_object_ids
    _validate_target_dict(db, account.id, selected)
    destination = _get_or_create_citizen_session(db, account, guest)
    row.status = "started"
    row.updated_at = datetime.now(UTC)
    db.add(row)
    # Duplicate saved benefits/reminders are safely merged into the citizen
    # session. They are not a migration blocker: the source row is deleted
    # only after the destination duplicate has been found, and all other
    # selected rows continue through the same transaction.
    _reown_selected(db, account, guest, destination, selected)
    row.status = "completed"
    row.source_deletion_status = "reowned"
    row.updated_at = datetime.now(UTC)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _migration_out(db, row, guest)


def _require_guest_proof(db_request: Request, db: Session, session_id: str) -> UserSession:
    supplied = db_request.headers.get("X-Guest-Session-Token", "").strip()
    if not supplied:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A guest session proof is required for migration",
        )
    row = db.exec(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.auth_mode == "guest",
            UserSession.access_token_hash == token_digest(supplied),
        )
    ).first()
    if row is None or (
        row.expires_at and _as_utc(row.expires_at) <= datetime.now(UTC)
    ):
        raise HTTPException(status_code=401, detail="The guest session proof is not valid")
    return row


def _validate_target(db: Session, account_id: str, payload: MigrationSelection) -> None:
    _validate_target_dict(db, account_id, _selection_dict(payload))


def _validate_target_dict(db: Session, account_id: str, selected: dict[str, list[str]]) -> None:
    household_id = next(iter(selected.get("target_household_id", [])), "")
    member_id = next(iter(selected.get("target_member_id", [])), "")
    if not household_id and (member_id or selected.get("profile_fact_keys")):
        raise HTTPException(
            status_code=400,
            detail="Choose a target household for profile migration",
        )
    if household_id:
        household = _owned_household(db, household_id, account_id)
        if member_id:
            _owned_member(db, household.id, member_id)
    if selected.get("profile_fact_keys") and not member_id:
        raise HTTPException(status_code=400, detail="Choose a target member for profile migration")


def _preview_items(
    db: Session,
    guest: UserSession,
    selected: dict[str, list[str]],
) -> tuple[list[MigrationItemOut], dict[str, list[str]]]:
    items: list[MigrationItemOut] = []
    conflicts: dict[str, list[str]] = {}
    selected_sets = {key: set(value) for key, value in selected.items()}
    for row in db.exec(select(SavedBenefit).where(SavedBenefit.session_id == guest.id)).all():
        if row.id in selected_sets["saved_benefit_ids"]:
            benefit = db.get(Benefit, row.benefit_id)
            items.append(
                MigrationItemOut(
                    kind="saved_benefit",
                    id=row.id,
                    title=benefit.name if benefit else row.benefit_id,
                    selected=True,
                )
            )
    _missing_selected(
        selected_sets["saved_benefit_ids"],
        {item.id for item in items if item.kind == "saved_benefit"},
        conflicts,
        "saved_benefit",
    )
    for row in db.exec(select(ApplicationTask).where(ApplicationTask.session_id == guest.id)).all():
        if row.id in selected_sets["task_ids"]:
            items.append(MigrationItemOut(kind="task", id=row.id, title=row.title, selected=True))
    _missing_selected(
        selected_sets["task_ids"],
        {item.id for item in items if item.kind == "task"},
        conflicts,
        "task",
    )
    for row in db.exec(select(Reminder).where(Reminder.session_id == guest.id)).all():
        if row.id in selected_sets["reminder_ids"]:
            benefit = db.get(Benefit, row.benefit_id)
            items.append(
                MigrationItemOut(
                    kind="reminder",
                    id=row.id,
                    title=benefit.name if benefit else row.benefit_id,
                    selected=True,
                )
            )
    _missing_selected(
        selected_sets["reminder_ids"],
        {item.id for item in items if item.kind == "reminder"},
        conflicts,
        "reminder",
    )
    for row in db.exec(select(ApplicationCase).where(ApplicationCase.session_id == guest.id)).all():
        if row.id in selected_sets["application_case_ids"]:
            items.append(
                MigrationItemOut(
                    kind="application_case",
                    id=row.id,
                    title=str(row.benefit_snapshot.get("name") or row.benefit_id),
                    selected=True,
                )
            )
    _missing_selected(
        selected_sets["application_case_ids"],
        {item.id for item in items if item.kind == "application_case"},
        conflicts,
        "application_case",
    )
    profile_keys = set(guest.profile or {})
    for key in selected_sets["profile_fact_keys"]:
        if key in profile_keys:
            items.append(MigrationItemOut(kind="profile_fact", id=key, title=key, selected=True))
    _missing_selected(
        selected_sets["profile_fact_keys"],
        {item.id for item in items if item.kind == "profile_fact"},
        conflicts,
        "profile_fact",
    )
    return items, conflicts


def _missing_selected(
    selected: set[str],
    present: set[str],
    conflicts: dict[str, list[str]],
    kind: str,
) -> None:
    missing = sorted(selected - present)
    if missing:
        conflicts[kind] = missing


def _reown_selected(
    db: Session,
    account: CitizenAccount,
    guest: UserSession,
    destination: UserSession,
    selected: dict[str, list[str]],
) -> dict[str, list[str]]:
    member_id = next(iter(selected.get("target_member_id", [])), "") or None
    for source in db.exec(select(SavedBenefit).where(SavedBenefit.session_id == guest.id)).all():
        if source.id not in selected.get("saved_benefit_ids", []):
            continue
        duplicate = db.exec(
            select(SavedBenefit).where(
                SavedBenefit.session_id == destination.id,
                SavedBenefit.benefit_id == source.benefit_id,
            )
        ).first()
        if duplicate is not None:
            db.delete(source)
            continue
        source.session_id = destination.id
        source.citizen_account_id = account.id
        source.household_member_id = member_id
        db.add(source)

    for source in db.exec(
        select(ApplicationTask).where(ApplicationTask.session_id == guest.id)
    ).all():
        if source.id not in selected.get("task_ids", []):
            continue
        duplicate = db.exec(
            select(ApplicationTask).where(
                ApplicationTask.session_id == destination.id,
                ApplicationTask.benefit_id == source.benefit_id,
                ApplicationTask.kind == source.kind,
                ApplicationTask.title == source.title,
            )
        ).first()
        if duplicate is not None:
            if source.status == "completed":
                duplicate.status = "completed"
                duplicate.completed_at = source.completed_at or datetime.now(UTC)
                db.add(duplicate)
            db.delete(source)
            continue
        source.session_id = destination.id
        source.citizen_account_id = account.id
        source.household_member_id = member_id
        db.add(source)

    for source in db.exec(select(Reminder).where(Reminder.session_id == guest.id)).all():
        if source.id not in selected.get("reminder_ids", []):
            continue
        duplicate = db.exec(
            select(Reminder).where(
                Reminder.session_id == destination.id,
                Reminder.benefit_id == source.benefit_id,
                Reminder.due_at == source.due_at,
                Reminder.channel == source.channel,
                Reminder.status == "scheduled",
            )
        ).first()
        if duplicate is not None:
            db.delete(source)
            continue
        source.session_id = destination.id
        db.add(source)

    for source in db.exec(
        select(ApplicationCase).where(ApplicationCase.session_id == guest.id)
    ).all():
        if source.id not in selected.get("application_case_ids", []):
            continue
        source.session_id = destination.id
        source.citizen_account_id = account.id
        source.household_member_id = member_id
        db.add(source)
        for task in db.exec(
            select(ApplicationTask).where(ApplicationTask.application_case_id == source.id)
        ).all():
            task.session_id = destination.id
            task.citizen_account_id = account.id
            task.household_member_id = member_id
            db.add(task)
        for reminder in db.exec(
            select(Reminder).where(Reminder.application_case_id == source.id)
        ).all():
            reminder.session_id = destination.id
            db.add(reminder)

    _migrate_profile_facts(db, account, guest, selected, member_id)
    return {}


def _migrate_profile_facts(
    db: Session,
    account: CitizenAccount,
    guest: UserSession,
    selected: dict[str, list[str]],
    member_id: str | None,
) -> None:
    if not selected.get("profile_fact_keys"):
        return
    household_id = next(iter(selected.get("target_household_id", [])), "")
    if not household_id or not member_id:
        raise HTTPException(status_code=400, detail="Profile migration needs a target member")
    for fact_key in selected.get("profile_fact_keys", []):
        raw_value = (guest.profile or {}).get(fact_key)
        if not isinstance(raw_value, (str, int, float)) or isinstance(raw_value, bool):
            raise HTTPException(
                status_code=409,
                detail="One selected profile fact is not migratable",
            )
        definition = db.exec(
            select(ProfileFactDefinition).where(
                ProfileFactDefinition.fact_key == fact_key,
                ProfileFactDefinition.scope == "member",
                ProfileFactDefinition.review_status == "approved",
            ).order_by(ProfileFactDefinition.version.desc())
        ).first()
        if definition is None:
            raise HTTPException(status_code=409, detail="One selected profile fact is not governed")
        value = _validate_fact_value(definition, str(raw_value))
        try:
            ciphertext = encrypt_profile_value(value)
            value_hash = profile_value_hash(value)
        except (ProfileDataEncryptionUnavailable, ValueError) as exc:
            raise HTTPException(
                status_code=503,
                detail="Profile migration storage is not configured",
            ) from exc
        existing = db.exec(
            select(ProfileFact).where(
                ProfileFact.household_id == household_id,
                ProfileFact.household_member_id == member_id,
                ProfileFact.fact_key == fact_key,
                ProfileFact.status == "current",
            )
        ).first()
        now = datetime.now(UTC)
        if existing is None:
            existing = ProfileFact(
                id=new_id("fact"),
                household_id=household_id,
                household_member_id=member_id,
                fact_key=fact_key,
                definition_version=definition.version,
                value_ciphertext=ciphertext,
                value_hash=value_hash,
                masked_value=mask_profile_value(value),
                value_source="citizen_confirmed_suggestion",
                purposes=["benefit_matching"],
                confirmed_by="citizen-migration",
                confirmed_at=now,
                revision=1,
            )
            action = "created"
            before = ""
        else:
            if existing.value_hash != value_hash:
                raise HTTPException(
                    status_code=409,
                    detail="A household fact has a different current value",
                )
            action = "confirmed"
            before = existing.masked_value
            existing.confirmed_at = now
            existing.revision += 1
        db.add(existing)
        db.add(
            ProfileFactRevision(
                id=new_id("factrev"),
                profile_fact_id=existing.id,
                revision=existing.revision,
                action=action,
                actor_id=account.id,
                reason="guest_to_citizen_migration",
                before_masked_value=before,
                after_masked_value=existing.masked_value,
                value_hash=value_hash,
                definition_version=definition.version,
            )
        )
        db.add(
            HouseholdConsentEvent(
                id=new_id("hconsent"),
                citizen_account_id=account.id,
                household_id=household_id,
                household_member_id=member_id,
                purpose="benefit_matching",
                action="granted",
                notice_version="household-radar-2026-08-09.v1",
                locale=account.preferred_language_code,
                actor_id="citizen-migration",
                safe_context={"fact_key": fact_key},
                created_at=now,
            )
        )
        guest.profile.pop(fact_key, None)
    db.add(guest)


def _get_or_create_citizen_session(
    db: Session,
    account: CitizenAccount,
    guest: UserSession,
) -> UserSession:
    existing = db.exec(
        select(UserSession).where(UserSession.phone_or_session_id == f"citizen:{account.id}")
    ).first()
    if existing is not None:
        return existing
    row = UserSession(
        id=new_id("citizen-session"),
        phone_or_session_id=f"citizen:{account.id}",
        auth_mode="citizen",
        state_code=guest.state_code,
        language_code=account.preferred_language_code or guest.language_code,
        profile={},
        expires_at=None,
    )
    db.add(row)
    db.flush()
    return row


def _selection_dict(payload: MigrationSelection) -> dict[str, list[str]]:
    return {
        "saved_benefit_ids": list(dict.fromkeys(payload.saved_benefit_ids)),
        "task_ids": list(dict.fromkeys(payload.task_ids)),
        "reminder_ids": list(dict.fromkeys(payload.reminder_ids)),
        "application_case_ids": list(dict.fromkeys(payload.application_case_ids)),
        "profile_fact_keys": list(dict.fromkeys(payload.profile_fact_keys)),
        "target_household_id": [payload.target_household_id] if payload.target_household_id else [],
        "target_member_id": [payload.target_member_id] if payload.target_member_id else [],
    }


def _has_selection(payload: MigrationSelection) -> bool:
    return any(
        (
            payload.saved_benefit_ids,
            payload.task_ids,
            payload.reminder_ids,
            payload.application_case_ids,
            payload.profile_fact_keys,
        )
    )


def _migration_out(
    db: Session,
    row: GuestMigration,
    guest: UserSession,
    *,
    items: list[MigrationItemOut] | None = None,
) -> MigrationOut:
    if items is None:
        items, _ = _preview_items(db, guest, row.selected_object_ids)
    selected = {
        key: value
        for key, value in row.selected_object_ids.items()
        if key not in {"target_household_id", "target_member_id"}
    }
    return MigrationOut(
        id=row.id,
        guest_session_id=guest.id,
        status=row.status,
        selected_object_ids=selected,
        items=items,
        conflict_report=dict(row.conflict_report or {}),
        source_deletion_status=row.source_deletion_status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
