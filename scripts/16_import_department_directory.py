"""Import an official department directory export as pending rows.

The importer never activates incoming records. A reviewer must inspect the
source, approve the row in the admin directory view, and only then can routing
use it. This prevents a scraped or stale contact list from silently becoming a
citizen-facing handoff target.

Usage:
    uv run python scripts/16_import_department_directory.py --file export.json
    uv run python scripts/16_import_department_directory.py --file export.json --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import select

from sahaayak_agent.bootstrap import ensure_reference_data
from sahaayak_common import (
    DepartmentDirectoryEntry,
    State,
    get_logger,
    init_db,
    new_id,
    session_scope,
)

log = get_logger(__name__)
ALLOWED_DOMAINS = {"scheme", "scholarship", "job", "citizen_support"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.file.read_text(encoding="utf-8"))
    records = payload.get("entries", []) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise SystemExit(
            "The directory export must be a JSON list or an "
            '{"entries": [...]} object'
        )

    init_db()
    ensure_reference_data()
    with session_scope() as db:
        created = updated = rejected = 0
        for index, raw in enumerate(records, start=1):
            try:
                data = _normalise(raw, index=index)
                if db.get(State, data["state_code"]) is None:
                    raise ValueError(f"unknown state_code {data['state_code']}")
            except (TypeError, ValueError, KeyError) as exc:
                rejected += 1
                log.warning("directory_record_rejected", row=index, reason=str(exc))
                continue

            existing = db.exec(
                select(DepartmentDirectoryEntry).where(
                    DepartmentDirectoryEntry.entry_key == data["entry_key"]
                )
            ).first()
            if args.dry_run:
                action = "update" if existing else "create"
                print(f"{action}: {data['entry_key']} · {data['department_name']}")
                continue

            if existing is None:
                db.add(DepartmentDirectoryEntry(id=new_id("dept"), **data))
                created += 1
                continue

            changed = _update_row(existing, data)
            db.add(existing)
            updated += int(changed)

        if args.dry_run:
            print(f"Dry run complete: {len(records)} source rows, {rejected} rejected.")
            return
        print(
            f"Directory import complete: {created} created, {updated} updated, "
            f"{rejected} rejected. Incoming rows remain pending until reviewed."
        )


def _normalise(raw: object, *, index: int) -> dict:
    if not isinstance(raw, dict):
        raise TypeError(f"row {index} is not an object")

    state_code = str(raw.get("state_code", "")).strip().upper()
    district_name = str(raw.get("district_name", "")).strip()[:120]
    service_domain = str(raw.get("service_domain", "citizen_support")).strip().lower()
    pincode = str(raw.get("pincode", "")).strip()
    pincode_prefix = str(raw.get("pincode_prefix", "")).strip()
    source_name = str(raw.get("source_name", "")).strip()[:160]
    source_url = str(raw.get("source_url", "")).strip()[:500]
    department_name = str(raw.get("department_name", "")).strip()[:200]
    if not state_code or not department_name:
        raise ValueError("state_code and department_name are required")
    if service_domain not in ALLOWED_DOMAINS:
        raise ValueError(f"service_domain must be one of {sorted(ALLOWED_DOMAINS)}")
    if pincode and (len(pincode) != 6 or not pincode.isdigit()):
        raise ValueError("pincode must be exactly six digits")
    if pincode_prefix and (not pincode_prefix.isdigit() or not 1 <= len(pincode_prefix) <= 5):
        raise ValueError("pincode_prefix must contain one to five digits")
    if not source_name or not source_url:
        raise ValueError("source_name and source_url are required")
    if not source_url.startswith(("https://", "http://")):
        raise ValueError("source_url must be an http(s) URL")

    source_last_verified = _parse_datetime(raw.get("source_last_verified"))
    source_record_id = str(raw.get("source_record_id", "")).strip()[:160]
    supplied_key = str(raw.get("entry_key", "")).strip()
    entry_key = supplied_key or _entry_key(
        state_code=state_code,
        district_name=district_name,
        service_domain=service_domain,
        pincode=pincode,
        pincode_prefix=pincode_prefix,
        department_code=str(raw.get("department_code", "")).strip(),
        source_record_id=source_record_id,
    )
    return {
        "entry_key": entry_key[:240],
        "state_code": state_code,
        "district_code": str(raw.get("district_code", "")).strip()[:80],
        "district_name": district_name,
        "service_domain": service_domain,
        "pincode": pincode,
        "pincode_prefix": pincode_prefix,
        "department_code": str(raw.get("department_code", "")).strip()[:120],
        "department_name": department_name,
        "help_centre_name": str(raw.get("help_centre_name", "")).strip()[:200],
        "address": str(raw.get("address", "")).strip()[:500],
        "phone": str(raw.get("phone", "")).strip()[:80],
        "email": str(raw.get("email", "")).strip()[:160],
        "website_url": str(raw.get("website_url", "")).strip()[:500],
        "source_name": source_name,
        "source_url": source_url,
        "source_record_id": source_record_id,
        "source_last_verified": source_last_verified,
        # Import is intentionally not an approval action.
        "approval_status": "pending",
        "is_active": False,
        "priority": max(0, min(int(raw.get("priority", 100)), 10_000)),
        "safe_metadata": (
            raw.get("safe_metadata")
            if isinstance(raw.get("safe_metadata"), dict)
            else {}
        ),
        "updated_at": datetime.now(UTC),
    }


def _update_row(row: DepartmentDirectoryEntry, data: dict) -> bool:
    comparable = {
        key: value
        for key, value in data.items()
        if key
        not in {
            "entry_key",
            "updated_at",
            "approval_status",
            "is_active",
            "source_last_verified",
        }
    }
    changed = any(
        _comparable_value(key, getattr(row, key), value) is False
        for key, value in comparable.items()
    )
    for key, value in data.items():
        if key not in {"entry_key", "approval_status", "is_active"}:
            setattr(row, key, value)
    if changed:
        row.approval_status = "pending"
        row.is_active = False
    return changed


def _comparable_value(key: str, existing: object, incoming: object) -> bool:
    """Compare source content without treating a fresh fetch as an edit.

    Public directory adapters refresh ``source_last_verified`` on every
    successful fetch. Approval should survive that refresh when the source
    record itself has not changed; a changed source snapshot still returns to
    the review queue. The stable hash in ``safe_metadata`` is preferred for
    adapter-produced rows and ordinary JSON imports continue to compare their
    metadata directly.
    """
    if key != "safe_metadata":
        return existing == incoming
    existing_metadata = existing if isinstance(existing, dict) else {}
    incoming_metadata = incoming if isinstance(incoming, dict) else {}
    existing_hash = existing_metadata.get("source_snapshot_hash")
    incoming_hash = incoming_metadata.get("source_snapshot_hash")
    if existing_hash and incoming_hash:
        return existing_hash == incoming_hash
    return existing_metadata == incoming_metadata


def _entry_key(**values: str) -> str:
    material = "|".join(values[key] for key in sorted(values))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"directory_{digest}"


def _parse_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


if __name__ == "__main__":
    main()
