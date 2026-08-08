"""Import Government jobs from an authorized National Career Service API.

NCS exposes a public job-search website, but the machine-readable API access
is account/terms dependent. This adapter therefore refuses to scrape a login
or undocumented browser endpoint. Provide the endpoint and key issued for the
NCS API portal, or use ``--input`` with an exported API response for a dry run.

All records are filtered to an explicit Government organisation marker and
remain inactive until a reviewer checks the original posting and application
link.

Usage:
    NCS_API_URL=https://... NCS_API_KEY=... \
      uv run --group pipeline python scripts/ingest_ncs_jobs.py --dry-run
    uv run --group pipeline python scripts/ingest_ncs_jobs.py --input ncs-response.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from sahaayak_common import REPO_ROOT, settings, slugify

DEFAULT_OUTPUT = REPO_ROOT / "data" / "structured" / "ncs_jobs.jsonl"
DEFAULT_SOURCE_OUTPUT = REPO_ROOT / "data" / "structured" / "ncs_job_sources.jsonl"
NCS_SEARCH_URL = "https://www.ncs.gov.in/Pages/Search.aspx?OT=National+Career+Service+portal"
NCS_ALLOWED_HOSTS = frozenset(
    {
        "ncs.gov.in",
        "www.ncs.gov.in",
        "portal.api.nationalcareers.service.gov.in",
    }
)

_STATE_CODES = {
    "andhra pradesh": "AP",
    "assam": "AS",
    "bihar": "BR",
    "chhattisgarh": "CG",
    "delhi": "DL",
    "goa": "GA",
    "gujarat": "GJ",
    "haryana": "HR",
    "himachal pradesh": "HP",
    "jharkhand": "JH",
    "karnataka": "KA",
    "kerala": "KL",
    "madhya pradesh": "MP",
    "maharashtra": "MH",
    "odisha": "OD",
    "punjab": "PB",
    "rajasthan": "RJ",
    "tamil nadu": "TN",
    "telangana": "TS",
    "uttar pradesh": "UP",
    "uttarakhand": "UK",
    "west bengal": "WB",
}


def _first(record: dict, *keys: str) -> object:
    for key in keys:
        value = record.get(key)
        if value not in (None, "", []):
            return value
    return ""


def _text(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(_text(item) for item in value if _text(item))
    if isinstance(value, dict):
        return ", ".join(f"{key}: {_text(item)}" for key, item in value.items())
    return str(value or "").strip()


def _government_marker(record: dict) -> bool:
    direct = _first(record, "is_government", "isGovernment", "government_job", "governmentJob")
    if isinstance(direct, bool):
        return direct
    marker = _text(
        _first(
            record,
            "organisation_type",
            "organization_type",
            "organisationType",
            "organizationType",
            "employer_type",
            "employerType",
        )
    ).casefold()
    return marker in {"government", "govt", "government employer", "public administration"}


def _allowed_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname in NCS_ALLOWED_HOSTS


def _parse_date(value: object) -> str | None:
    raw = _text(value)
    if not raw:
        return None
    normalized = raw.replace("/", "-").replace(".", "-")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%m-%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(normalized[:19], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _state_code(value: object) -> str | None:
    raw = _text(value).casefold()
    if len(raw) == 2 and raw.upper() in set(_STATE_CODES.values()):
        return raw.upper()
    return _STATE_CODES.get(raw)


def _education_level(value: object) -> str | None:
    lowered = _text(value).casefold()
    if not lowered:
        return None
    if any(term in lowered for term in ("ph.d", "phd", "doctorate")):
        return "PhD"
    if any(term in lowered for term in ("post graduate", "postgraduate", "master")):
        return "PG"
    if any(term in lowered for term in ("bachelor", "graduate", "degree", "ug")):
        return "UG"
    if any(term in lowered for term in ("diploma", "iti", "polytechnic")):
        return "iti_diploma"
    if any(term in lowered for term in ("12th", "class 12", "puc", "intermediate")):
        return "class_12"
    if any(term in lowered for term in ("10th", "class 10", "sslc", "matric")):
        return "class_10"
    return None


def _experience_years(value: object) -> int | None:
    match = re.search(r"\b(\d+)\s*\+?\s*years?", _text(value), flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _records(payload: object) -> list[dict]:
    """Find the common list envelopes without trusting arbitrary nested data."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("jobs", "results", "items", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return _records(data)
    return []


def parse_job(record: dict, *, checked_on: date | None = None) -> tuple[dict, dict] | None:
    """Normalize one explicit NCS Government record into DB and RAG rows."""
    if not _government_marker(record):
        return None
    checked_on = checked_on or date.today()
    job_id = _text(_first(record, "id", "job_id", "jobId", "vacancy_id", "vacancyId"))
    title = _text(_first(record, "title", "job_title", "jobTitle", "designation", "name"))
    if not title:
        return None
    source_url = _text(_first(record, "source_url", "sourceUrl", "ncs_url", "ncsUrl"))
    if not _allowed_url(source_url):
        source_url = NCS_SEARCH_URL
    application_url = _text(
        _first(record, "application_url", "applicationUrl", "apply_url", "applyUrl", "url")
    )
    if not application_url.startswith("https://"):
        application_url = source_url
    employer = _text(
        _first(record, "employer", "employer_name", "employerName", "organisation_name")
    )
    state = _state_code(_first(record, "state", "state_name", "stateName", "job_location_state"))
    locations = _text(_first(record, "locations", "location", "job_location", "jobLocation"))
    education = _education_level(
        _first(record, "education", "education_level", "educationLevel", "qualification")
    )
    experience = _experience_years(
        _first(record, "experience", "experience_required", "experienceRequired")
    )
    deadline = _parse_date(
        _first(
            record,
            "application_deadline",
            "applicationDeadline",
            "last_date",
            "lastDate",
            "closing_date",
        )
    )

    canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    source_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    stable_id = job_id or source_hash[:20]
    row_id = slugify(f"ncs-{stable_id}-{title}")
    criteria: dict[str, object] = {
        "education_level": [education] if education else None,
        "min_experience_years": experience,
        "locations": [locations] if locations else None,
        "exclusions": [
            "Age, reservation, fee, and qualification equivalence must be checked "
            "in the original NCS posting."
        ],
    }
    criteria = {key: value for key, value in criteria.items() if value not in (None, [])}
    source_title = f"National Career Service · {title}"
    row = {
        "id": row_id,
        "domain": "job",
        "name": title,
        "state_code": state,
        "category": "Government Jobs",
        "description": f"{title} listed through the National Career Service Government jobs feed.",
        "eligibility_initial": criteria,
        "benefits_text": (
            "Government job listing; terms and selection conditions are stated "
            "in the official posting."
        ),
        "documents_required": [],
        "application_process": (
            "Read the original NCS posting and apply only through the listed "
            f"official link: {application_url}"
        ),
        "source_url": source_url,
        "source_title": source_title,
        "source_document_url": source_url,
        "source_excerpt": canonical[:8000],
        "source_content_hash": source_hash,
        "verification_status": "machine_structured",
        "last_verified_date": checked_on.isoformat(),
        "valid_until": deadline,
        "is_active": False,
        "job_metadata": {
            "source_kind": "ncs_government_jobs_api",
            "ncs_job_id": job_id,
            "employer": employer,
            "organisation_type": _text(
                _first(record, "organisation_type", "organization_type", "employer_type")
            ),
            "locations": locations,
            "application_deadline": deadline,
            "application_url": application_url,
        },
        "automated_review": {
            "reviewer": "ncs_api_normalizer",
            "source": "National Career Service Government jobs feed",
            "review_required": True,
            "review_fields": [
                "employer",
                "title",
                "qualification",
                "age_and_reservation",
                "deadline",
                "application_url",
            ],
        },
    }
    source_row = {
        "source_id": slugify(f"ncs-{stable_id}-{title}"),
        "filename": f"ncs-{stable_id}.json",
        "raw_text": canonical,
        "source_hash": source_hash,
        "source_url": source_url,
        "source_title": source_title,
        "dataset": "ncs_government_jobs",
        "verification": "raw_machine_extracted",
    }
    return row, source_row


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_input(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read NCS JSON input {path}: {exc}") from exc


def _fetch(api_url: str, api_key: str, *, limit: int, timeout: float) -> object:
    if not _allowed_url(api_url):
        raise SystemExit(
            "NCS_API_URL must be an HTTPS endpoint on the NCS API allowlist. "
            "Confirm the endpoint and terms with NCS before configuring it."
        )
    headers = {"User-Agent": "SahaayakJobImporter/0.1 (NCS review queue)"}
    if api_key:
        headers["X-API-Key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            response = client.get(
                api_url,
                params={"organisation_type": "Government", "page": 1, "page_size": limit},
            )
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SystemExit(
            f"NCS API request failed: {exc}. The exact API auth and query fields "
            "must match the account's current developer documentation."
        ) from exc


def run(
    *,
    payload: object,
    output: Path,
    source_output: Path,
    limit: int,
    dry_run: bool,
) -> int:
    rows: list[dict] = []
    sources: list[dict] = []
    for record in _records(payload)[:limit]:
        parsed = parse_job(record)
        if parsed is None:
            continue
        row, source = parsed
        rows.append(row)
        sources.append(source)

    print(f"Government records accepted: {len(rows)}")
    if dry_run:
        for row in rows:
            print(f"- {row['name']} · deadline {row['valid_until'] or 'not stated'}")
        return len(rows)
    _write_jsonl(output, rows)
    _write_jsonl(source_output, sources)
    print(f"Wrote inactive review queue to {output}")
    print(f"Wrote source text for RAG ingestion to {source_output}")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=os.getenv("NCS_API_URL") or settings.ncs_api_url)
    parser.add_argument("--api-key", default=os.getenv("NCS_API_KEY") or settings.ncs_api_key)
    parser.add_argument(
        "--input",
        type=Path,
        help="Use an exported API JSON response instead of the network",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-output", type=Path, default=DEFAULT_SOURCE_OUTPUT)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    limit = max(1, min(args.limit, 500))
    payload = (
        _load_input(args.input)
        if args.input
        else _fetch(
            args.api_url,
            args.api_key,
            limit=limit,
            timeout=max(1.0, min(args.timeout, 120.0)),
        )
    )
    run(
        payload=payload,
        output=args.output,
        source_output=args.source_output,
        limit=limit,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
