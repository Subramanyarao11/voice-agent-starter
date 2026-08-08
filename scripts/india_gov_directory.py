"""Client and normalizer for India.gov's structured contact directory feed.

The public India.gov contact directory exposes state/UT department and
district records through an official JSON endpoint. This module deliberately
keeps the source-specific HTTP code separate from the database importer:
fetching produces a reviewable JSON snapshot, while importing it still goes
through ``16_import_department_directory.py`` and its pending-row gate.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

INDIA_GOV_API_URL = "https://www.india.gov.in/directory/contact-directory/api"
INDIA_GOV_STATE_DIRECTORY_URL = (
    "https://www.india.gov.in/directory/contact-directory/state-uts"
)
DEFAULT_ORGANIZATION_TYPES = ("E003", "E004", "E042")
ORGANIZATION_TYPE_NAMES = {
    "E003": "Departments",
    "E004": "Directorates / Commissionerates",
    "E042": "Districts",
    "SPMA": "Schemes / Programmes / Missions / Applications",
}


class IndiaGovDirectoryError(RuntimeError):
    """Raised when the official source returns an unusable response."""


class IndiaGovDirectoryClient:
    """Small, bounded client for the endpoint used by India.gov itself."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
            transport=transport,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Sahaayak-directory-ingest/1.0 (+official-source-review)",
            },
        )

    def close(self) -> None:
        self._client.close()

    def states(self) -> list[dict[str, Any]]:
        payload = {"dataval": {"pageno": 1, "pageSize": 100, "querytype": "All_States"}}
        result = self._post(payload)
        return _result_list(result, "getIgodAllState")

    def state_records(
        self,
        state_code: str,
        *,
        organization_types: Iterable[str] = DEFAULT_ORGANIZATION_TYPES,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        normalized_state = state_code.strip().upper()
        for organization_type in organization_types:
            type_code = organization_type.strip().upper()
            payload = {
                "dataval": {
                    "clientvalue": "client2",
                    "pageno": 1,
                    "pageSize": 10_000,
                    "mustvalue": [
                        {"fieldName": "category", "fieldValue": "sg"},
                        {"fieldName": "state_id", "fieldValue": normalized_state},
                    ],
                    "shouldvalue": [
                        {"fieldName": "organization_type", "fieldValue": type_code}
                    ],
                    "querytype": "State_Contact_Directory_with_category_filter",
                }
            }
            result = self._post(payload)
            for row in _result_list(result, "getIgodWebDirectoryByFilters"):
                if isinstance(row, dict):
                    rows.append({**row, "_organization_type": type_code})
        return rows

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(INDIA_GOV_API_URL, json=payload)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise IndiaGovDirectoryError(f"India.gov directory request failed: {exc}") from exc
        if not isinstance(body, dict) or not isinstance(body.get("resultdata"), dict):
            raise IndiaGovDirectoryError("India.gov directory response has no resultdata object")
        return body


def normalize_records(
    *,
    state: Mapping[str, Any],
    records: Iterable[Mapping[str, Any]],
    fetched_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Convert source rows into the importer's stable directory JSON shape."""
    state_code = _clean(state.get("state_id"), upper=True)
    state_name = _clean(state.get("stateName"))
    if not state_code or not state_name:
        raise ValueError("India.gov state rows need state_id and stateName")
    verified_at = (fetched_at or datetime.now(UTC)).astimezone(UTC)
    source_url = f"{INDIA_GOV_STATE_DIRECTORY_URL}/{state_code.casefold()}"
    normalized: list[dict[str, Any]] = []
    for record in records:
        title = _clean(record.get("title"))
        organization_type = _clean(record.get("_organization_type"), upper=True)
        if not title or not organization_type:
            continue
        category = ORGANIZATION_TYPE_NAMES.get(
            organization_type,
            _clean(record.get("orgName")) or "Government organization",
        )
        is_district = organization_type == "E042"
        primary_url = _http_url(record.get("url"))
        contact_url = _http_url(record.get("url_1"))
        website_url = contact_url or primary_url
        stable_source = {
            "state_code": state_code,
            "organization_type": organization_type,
            "title": title,
            "primary_url": primary_url,
            "contact_url": contact_url,
        }
        snapshot_hash = hashlib.sha256(
            _stable_json(stable_source).encode("utf-8")
        ).hexdigest()
        record_slug = _slug(f"{state_code}-{organization_type}-{title}")
        normalized.append(
            {
                "state_code": state_code,
                "district_name": title if is_district else "",
                "service_domain": "citizen_support",
                "department_code": organization_type,
                "department_name": (
                    f"{title} District Administration" if is_district else title
                ),
                "help_centre_name": title,
                "website_url": website_url,
                "source_name": "India.gov.in Integrated Government Online Directory",
                "source_url": source_url,
                "source_record_id": f"{state_code}:{organization_type}:{record_slug}",
                "source_last_verified": verified_at.isoformat(),
                "priority": 80 if is_district else 100,
                "safe_metadata": {
                    "source_kind": "india_gov_contact_directory",
                    "source_category": category,
                    "source_scope": "district" if is_district else "state",
                    "source_state_name": state_name,
                    "source_snapshot_hash": snapshot_hash,
                    "source_fetched_at": verified_at.isoformat(),
                    "source_primary_url": primary_url,
                    "source_contact_url": contact_url,
                },
            }
        )
    return normalized


def _result_list(body: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    try:
        data = body["resultdata"]["data"][key]
        result = data["results"]
    except (KeyError, TypeError) as exc:
        raise IndiaGovDirectoryError(f"India.gov response is missing {key}.results") from exc
    if not isinstance(result, list):
        raise IndiaGovDirectoryError(f"India.gov {key}.results is not a list")
    return [row for row in result if isinstance(row, dict)]


def _clean(value: Any, *, upper: bool = False) -> str:
    text = str(value or "").strip()
    return text.upper() if upper else text[:500]


def _http_url(value: Any) -> str:
    text = _clean(value)
    return text if text.startswith(("https://", "http://")) else ""


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:120]


def _stable_json(value: Mapping[str, Any]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
