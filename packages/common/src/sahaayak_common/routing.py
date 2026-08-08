"""Safe default routing for human handoffs.

The application can route a ticket by the caller's state, domain, and stated
location without pretending that it knows the current government directory.
An operator can replace this fallback on the ticket, and the source field is
kept so later directory integrations can be measured separately.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from sahaayak_common.models import DepartmentDirectoryEntry
from sahaayak_common.settings import settings
from sahaayak_contracts import Domain

_STATE_NAMES = {
    "AP": "Andhra Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CG": "Chhattisgarh",
    "DL": "Delhi",
    "GJ": "Gujarat",
    "HR": "Haryana",
    "HP": "Himachal Pradesh",
    "JH": "Jharkhand",
    "KA": "Karnataka",
    "KL": "Kerala",
    "MP": "Madhya Pradesh",
    "MH": "Maharashtra",
    "MN": "Manipur",
    "ML": "Meghalaya",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "PB": "Punjab",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TS": "Telangana",
    "TR": "Tripura",
    "UK": "Uttarakhand",
    "UP": "Uttar Pradesh",
    "WB": "West Bengal",
    "JK": "Jammu and Kashmir",
    "LA": "Ladakh",
    "PY": "Puducherry",
    "CH": "Chandigarh",
    "AN": "Andaman and Nicobar Islands",
    "GA": "Goa",
    # India.gov's current state/UT directory code is ND. Keep DN as a
    # backwards-compatible alias for older manually imported rows.
    "ND": "Dadra and Nagar Haveli and Daman and Diu",
    "DN": "Dadra and Nagar Haveli and Daman and Diu",
    "AR": "Arunachal Pradesh",
    "CT": "Chhattisgarh",
}

_DOMAIN_LABELS = {
    Domain.SCHEME: "welfare schemes helpdesk",
    Domain.SCHOLARSHIP: "education and scholarships helpdesk",
    Domain.JOB: "employment and careers helpdesk",
}


@dataclass(frozen=True)
class EscalationRoute:
    department: str
    routing_location: str
    routing_source: str
    directory_entry_id: str | None = None
    source_url: str = ""
    verified_at: datetime | None = None


def resolve_escalation_route(
    *,
    state_code: str | None,
    domain: Domain | None,
    slots: Mapping[object, object] | None = None,
    db: Session | None = None,
) -> EscalationRoute:
    """Return an approved directory route or a clearly labelled fallback.

    `location` is only a caller-stated city/district value. It is never
    geocoded or treated as a verified pincode. When ``db`` is supplied, an
    approved and recently verified directory entry can improve the route; an
    unapproved or stale row is deliberately ignored.
    """

    normalized_state = (state_code or "").strip().upper()
    state_name = _STATE_NAMES.get(normalized_state, "National")
    label = _DOMAIN_LABELS.get(domain, "citizen-support helpdesk")
    department = f"{state_name} {label}"

    location = ""
    for key, value in (slots or {}).items():
        key_value = getattr(key, "value", key)
        if key_value == "location" and value is not None:
            location = str(value).strip()[:120]
            break

    fallback = EscalationRoute(
        department=department[:160],
        routing_location=location,
        routing_source="state_domain_fallback",
    )
    if db is None:
        return fallback

    directory_route = _resolve_directory_route(
        db,
        state_code=normalized_state,
        domain=domain,
        location=location,
    )
    return directory_route or fallback


def _resolve_directory_route(
    db: Session,
    *,
    state_code: str,
    domain: Domain | None,
    location: str,
) -> EscalationRoute | None:
    if not state_code:
        return None

    domain_value = getattr(domain, "value", "")
    service_domains = ["citizen_support"]
    if domain_value:
        service_domains.insert(0, domain_value)
    rows = db.exec(
        select(DepartmentDirectoryEntry).where(
            DepartmentDirectoryEntry.state_code == state_code,
            DepartmentDirectoryEntry.service_domain.in_(service_domains),
            DepartmentDirectoryEntry.approval_status == "approved",
            DepartmentDirectoryEntry.is_active.is_(True),
        )
    ).all()
    if not rows:
        return None

    verified_after = datetime.now(UTC) - timedelta(
        days=max(1, settings.department_directory_stale_days)
    )
    pincode = _extract_pincode(location)
    district = _district_hint(location)

    fresh_rows = [
        row
        for row in rows
        if row.source_last_verified is not None
        and _aware(row.source_last_verified) >= verified_after
        and (row.valid_until is None or row.valid_until >= datetime.now(UTC).date())
    ]
    matching_rows = [
        row
        for row in fresh_rows
        if _directory_entry_matches(row, pincode=pincode, district=district)
    ]
    if not matching_rows:
        return None

    # Several state-wide departments can be valid source records without any
    # one of them being the right destination for an arbitrary citizen. Use a
    # specific district/postal match whenever one exists; otherwise accept a
    # state-wide directory route only when it is unambiguous. This prevents a
    # caller who only supplied a pincode from being sent to whichever imported
    # state department happened to sort first.
    specific_rows = [
        row for row in matching_rows if row.district_name or row.pincode or row.pincode_prefix
    ]
    if specific_rows:
        matching_rows = specific_rows
    elif len(matching_rows) != 1:
        return None

    selected = max(
        matching_rows,
        key=lambda row: _directory_match_score(
            row,
            pincode=pincode,
            district=district,
            domain=domain_value,
        ),
    )
    return EscalationRoute(
        department=selected.department_name[:160],
        routing_location=(selected.district_name or location)[:120],
        routing_source="authoritative_directory",
        directory_entry_id=selected.id,
        source_url=selected.source_url,
        verified_at=selected.source_last_verified,
    )


def _directory_entry_matches(
    entry: DepartmentDirectoryEntry,
    *,
    pincode: str,
    district: str,
) -> bool:
    if pincode and entry.pincode == pincode:
        return True
    if pincode and entry.pincode_prefix and pincode.startswith(entry.pincode_prefix):
        return True
    if district and _normalise_text(entry.district_name) == district:
        return True
    return (
        # A source-attested state-wide department is a valid last directory
        # choice when a more specific district/postal record is unavailable.
        # Exact pincode/prefix/district rows still outrank it in the score.
        not entry.district_name
        and not entry.pincode
        and not entry.pincode_prefix
    )


def _directory_match_score(
    entry: DepartmentDirectoryEntry,
    *,
    pincode: str,
    district: str,
    domain: str,
) -> tuple[int, int, int, int, int, float]:
    exact_pincode = int(bool(pincode and entry.pincode == pincode))
    prefix_length = (
        len(entry.pincode_prefix)
        if pincode and pincode.startswith(entry.pincode_prefix)
        else 0
    )
    exact_district = int(bool(district and _normalise_text(entry.district_name) == district))
    exact_domain = int(bool(domain and entry.service_domain == domain))
    verified_at = (
        _aware(entry.source_last_verified).timestamp()
        if entry.source_last_verified
        else 0.0
    )
    return (
        exact_pincode,
        prefix_length,
        exact_district,
        exact_domain,
        -entry.priority,
        verified_at,
    )


def _extract_pincode(location: str) -> str:
    match = re.search(r"(?<!\d)(\d{6})(?!\d)", location)
    return match.group(1) if match else ""


def _district_hint(location: str) -> str:
    value = _normalise_text(location)
    return re.sub(r"\s+district$", "", value).strip()


def _normalise_text(value: str) -> str:
    return " ".join(value.casefold().replace(",", " ").split())


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
