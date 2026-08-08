"""Import official state recruitment notifications into the review queue.

The first state adapter is Karnataka Public Service Commission (KPSC). State
government sites publish a mixture of recruitment notifications, corrigenda,
selection lists, results, tenders, and departmental notices on the same page.
This importer follows only HTTPS PDF links on an allowlisted official host and
keeps only notification-shaped entries. Every row remains inactive until a
reviewer checks the notification.

Usage:
    uv run --group pipeline python scripts/ingest_state_jobs.py --dry-run
    uv run --group pipeline python scripts/ingest_state_jobs.py
    uv run python scripts/04_seed_db.py --file data/structured/state_jobs.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import pdfplumber

from sahaayak_common import REPO_ROOT, slugify

DEFAULT_OUTPUT = REPO_ROOT / "data" / "structured" / "state_jobs.jsonl"
DEFAULT_SOURCE_OUTPUT = REPO_ROOT / "data" / "structured" / "state_job_sources.jsonl"
MAX_PDF_BYTES = 30 * 1024 * 1024
USER_AGENT = "SahaayakJobImporter/0.1 (official-source review queue)"


@dataclass(frozen=True)
class StateJobSource:
    state_code: str
    authority: str
    index_url: str
    allowed_hosts: frozenset[str]
    application_url: str
    source_kind: str


STATE_SOURCES = {
    "KA": StateJobSource(
        state_code="KA",
        authority="Karnataka Public Service Commission",
        index_url="https://kpsc.kar.nic.in/notification.html",
        allowed_hosts=frozenset({"kpsc.kar.nic.in"}),
        application_url="https://kpsconline.karnataka.gov.in/Home",
        source_kind="kpsc_recruitment_notification",
    ),
}

# A notification page is not a recruitment-only feed. These are deliberately
# conservative exclusions: false negatives create a review task; false
# positives can present a result list or a cancelled notice as an open job.
_EXCLUDED_TITLE_TERMS = (
    "cancellation",
    "cancelled",
    "corrigendum",
    "result",
    "select list",
    "selection list",
    "provisional list",
    "final list",
    "cut-off",
    "cutoff",
    "departmental examination",
    "time table",
    "timetable",
    "press note",
    "pressnote",
    "tender",
    "syllabus",
    "hall ticket",
    "answer key",
    "seniority",
)
_INCLUDE_TITLE_TERMS = ("notification", "recruitment", "vacancy", "posts")
_DATE_PATTERNS = (
    r"(?:last|closing|close|submission)[^0-9]{0,100}(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})",
    r"(?:apply|application)[^0-9]{0,100}(?:before|by|till|upto|up to)?[^0-9]{0,30}"
    r"(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})",
)


class _AnchorParser(HTMLParser):
    """Collect anchor text without requiring a third-party HTML parser."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._href = ""
        self._text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        self._href = next((value or "" for key, value in attrs if key.lower() == "href"), "")
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href:
            return
        self.links.append((self._href, " ".join(self._text)))
        self._href = ""
        self._text = []


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def is_official_url(value: str, *, allowed_hosts: frozenset[str]) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname in allowed_hosts


def extract_pdf_links(
    html: str,
    *,
    base_url: str,
    allowed_hosts: frozenset[str],
) -> list[tuple[str, str]]:
    """Return filtered official PDF links from a state notification page."""
    parser = _AnchorParser()
    parser.feed(html)
    links: list[tuple[str, str]] = []
    for href, raw_title in parser.links:
        absolute = urljoin(base_url, unescape(href))
        if not absolute.lower().split("?", 1)[0].endswith(".pdf"):
            continue
        if not is_official_url(absolute, allowed_hosts=allowed_hosts):
            continue
        title = _clean_text(raw_title) or Path(urlparse(absolute).path).name
        lowered = title.casefold()
        if any(term in lowered for term in _EXCLUDED_TITLE_TERMS):
            continue
        if not any(term in lowered for term in _INCLUDE_TITLE_TERMS):
            continue
        links.append((title, absolute))
    return list(dict.fromkeys(links))


def _parse_date(value: str) -> str | None:
    normalized = value.replace("/", "-").replace(".", "-")
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _deadline(text: str) -> str | None:
    for pattern in _DATE_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            parsed = _parse_date(match.group(1))
            if parsed:
                return parsed
    return None


def _vacancy_count(title: str, text: str) -> int | None:
    haystack = f"{title} {text}"
    match = re.search(r"\b(\d[\d,]*)\s+(?:posts?|vacanc(?:y|ies))\b", haystack, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def _extract_text(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def parse_notification(
    text: str,
    *,
    source_url: str,
    listing_title: str,
    source: StateJobSource,
    source_content_hash: str,
    checked_on: date | None = None,
) -> dict:
    """Create one conservative, inactive job row per state notification.

    State notifications vary too much for a generic parser to safely infer
    age, reservation, qualification equivalence, or post-by-post vacancies.
    Those fields are intentionally left for the review queue instead of being
    guessed from a PDF that may be in a regional script.
    """
    checked_on = checked_on or date.today()
    title = _clean_text(listing_title)[:240] or "State government recruitment notification"
    excerpt = re.sub(r"\s+", " ", text).strip()[:8000]
    deadline = _deadline(text)
    count = _vacancy_count(title, text)
    row_id = slugify(f"{source.state_code}-{source.authority}-{title}-{source_url}")
    return {
        "id": row_id,
        "domain": "job",
        "name": title,
        "state_code": source.state_code,
        "category": "State Government Jobs",
        "description": f"{title} published by {source.authority}.",
        "eligibility_initial": {
            "locations": ["Karnataka"],
            "exclusions": [
                "Age, reservation, qualification equivalence, fee, and post-specific "
                "conditions must be checked in the official notification."
            ],
        },
        "benefits_text": (
            "State government recruitment post; service conditions are stated "
            "in the official notification."
        ),
        "documents_required": [],
        "application_process": (
            "Read the official notification and apply through the authorised "
            f"portal: {source.application_url}."
        ),
        "source_url": source_url,
        "source_title": f"{source.authority} · {title}",
        "source_document_url": source_url,
        "source_excerpt": excerpt,
        "source_content_hash": source_content_hash,
        "verification_status": "machine_structured",
        "last_verified_date": checked_on.isoformat(),
        "valid_until": deadline,
        "is_active": False,
        "job_metadata": {
            "source_kind": source.source_kind,
            "authority": source.authority,
            "state_code": source.state_code,
            "vacancy_count": count,
            "application_deadline": deadline,
            "application_url": source.application_url,
            "parser_note": "Post-specific fields require human review of the notification.",
        },
        "automated_review": {
            "reviewer": "official_state_source_parser",
            "source": source.authority,
            "review_required": True,
            "review_fields": [
                "title",
                "post_count",
                "qualification",
                "age_and_reservation",
                "deadline",
                "documents",
                "application_url",
            ],
        },
    }


def _curl_fetch(url: str, *, timeout: float) -> bytes:
    """Fetch a validated official URL when a legacy server breaks HTTPX parsing."""
    try:
        result = subprocess.run(
            [
                "curl",
                "--fail",
                "--location",
                "--silent",
                "--show-error",
                "--max-time",
                str(max(1.0, timeout)),
                "--user-agent",
                USER_AGENT,
                "--url",
                url,
            ],
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError("curl is required for this legacy official source") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"curl failed for official source: {detail or result.returncode}")
    return result.stdout


def _fetch_pdf(
    client: httpx.Client,
    url: str,
    *,
    allowed_hosts: frozenset[str],
    timeout: float,
) -> bytes:
    if not is_official_url(url, allowed_hosts=allowed_hosts):
        raise ValueError(f"Refusing non-official state URL: {url}")
    try:
        response = client.get(url)
        response.raise_for_status()
        content = response.content
    except httpx.RemoteProtocolError:
        content = _curl_fetch(url, timeout=timeout)
    if len(content) > MAX_PDF_BYTES:
        raise ValueError(f"Document exceeds the {MAX_PDF_BYTES} byte limit: {url}")
    return content


def _fetch_index(client: httpx.Client, source: StateJobSource, *, timeout: float) -> str:
    try:
        response = client.get(source.index_url)
        response.raise_for_status()
        return response.text
    except httpx.RemoteProtocolError:
        return _curl_fetch(source.index_url, timeout=timeout).decode(
            "utf-8", errors="replace"
        )


def run(
    *,
    source: StateJobSource,
    output: Path,
    source_output: Path,
    limit: int,
    dry_run: bool,
    timeout: float,
) -> int:
    if not is_official_url(source.index_url, allowed_hosts=source.allowed_hosts):
        raise SystemExit("The state job importer only accepts an HTTPS allowlisted index URL.")

    headers = {"User-Agent": USER_AGENT}
    cache = REPO_ROOT / "data" / "jobs" / "states" / source.state_code.casefold()
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        links = extract_pdf_links(
            _fetch_index(client, source, timeout=timeout),
            base_url=source.index_url,
            allowed_hosts=source.allowed_hosts,
        )[:limit]
        if not links:
            raise SystemExit(
                "No recruitment-shaped official PDFs were found at "
                f"{source.index_url}."
            )

        rows: list[dict] = []
        sources: list[dict] = []
        for listing_title, pdf_url in links:
            pdf_bytes = _fetch_pdf(
                client,
                pdf_url,
                allowed_hosts=source.allowed_hosts,
                timeout=timeout,
            )
            cache.mkdir(parents=True, exist_ok=True)
            filename = Path(urlparse(pdf_url).path).name or "notification.pdf"
            (cache / filename).write_bytes(pdf_bytes)
            extracted_text = _extract_text(pdf_bytes)
            content_hash = hashlib.sha256(pdf_bytes).hexdigest()
            rows.append(
                parse_notification(
                    extracted_text,
                    source_url=pdf_url,
                    listing_title=listing_title,
                    source=source,
                    source_content_hash=content_hash,
                )
            )
            sources.append(
                {
                    "source_id": slugify(f"{source.state_code}-{listing_title}-{filename}"),
                    "filename": filename,
                    "raw_text": extracted_text,
                    "source_hash": content_hash,
                    "source_url": pdf_url,
                    "source_title": f"{source.authority} · {listing_title}",
                    "dataset": "state_government_jobs",
                    "verification": "raw_machine_extracted",
                }
            )
            print(f"{listing_title}: extracted 1 notification")

    print(f"Total machine-structured state job notifications: {len(rows)}")
    if dry_run:
        for row in rows:
            print(f"- {row['name']} · deadline {row['valid_until'] or 'not machine-extracted'}")
        return len(rows)

    _write_jsonl(output, rows)
    _write_jsonl(source_output, sources)
    print(f"Wrote inactive review queue to {output}")
    print(f"Wrote source text for RAG ingestion to {source_output}")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-code", choices=tuple(STATE_SOURCES), default="KA")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-output", type=Path, default=DEFAULT_SOURCE_OUTPUT)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(
        source=STATE_SOURCES[args.state_code],
        output=args.output,
        source_output=args.source_output,
        limit=max(1, min(args.limit, 20)),
        dry_run=args.dry_run,
        timeout=max(1.0, min(args.timeout, 120.0)),
    )


if __name__ == "__main__":
    main()
