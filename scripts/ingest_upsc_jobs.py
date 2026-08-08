"""Import current UPSC recruitment advertisements into the job review queue.

This is intentionally a narrow, official-source adapter. It fetches the UPSC
advertisement index, follows only UPSC PDF links, extracts posting-shaped
metadata, and writes rows compatible with scripts/04_seed_db.py. It does
not call an LLM and it never publishes a posting: every row is
machine_structured and inactive until a reviewer checks the notification.

Usage:
    uv run --group pipeline python scripts/ingest_upsc_jobs.py --dry-run
    uv run --group pipeline python scripts/ingest_upsc_jobs.py
    uv run python scripts/04_seed_db.py --file data/structured/jobs.jsonl

The raw PDFs are kept in the ignored data/jobs/upsc directory. Re-running
the command refreshes the current advertisement set; expired records are not
deleted from the database automatically so their history remains auditable.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from datetime import date, datetime
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import pdfplumber

from sahaayak_common import REPO_ROOT, slugify

INDEX_URL = "https://www.upsc.gov.in/recruitment/recruitment-advertisement"
ALLOWED_HOSTS = frozenset({"upsc.gov.in", "www.upsc.gov.in"})
DEFAULT_OUTPUT = REPO_ROOT / "data" / "structured" / "jobs.jsonl"
DEFAULT_SOURCE_OUTPUT = REPO_ROOT / "data" / "structured" / "job_sources.jsonl"
PDF_CACHE = REPO_ROOT / "data" / "jobs" / "upsc"
MAX_PDF_BYTES = 25 * 1024 * 1024

_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_DATE_RE = r"\d{2}-\d{2}-\d{4}"
_POST_RE = re.compile(
    r"(?m)^\s*(?P<ordinal>\d+)\.\s*\(Vacancy No\.\s*(?P<vacancy>[^)]+)\)"
)


def _clean_html(value: str) -> str:
    text = unescape(re.sub(r"<[^>]+>", " ", value))
    return re.sub(r"\s+", " ", text).strip()


def _is_official_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname in ALLOWED_HOSTS


def extract_pdf_links(html: str, *, base_url: str = INDEX_URL) -> list[tuple[str, str]]:
    """Extract labelled PDF links from the official index, with host gating."""
    links: list[tuple[str, str]] = []
    for item in re.findall(r"<li\b[^>]*>.*?</li>", html, flags=re.IGNORECASE | re.DOTALL):
        href_match = re.search(
            r"href\s*=\s*[\"']([^\"']+\.pdf(?:\?[^\"']*)?)[\"']",
            item,
            flags=re.IGNORECASE,
        )
        if not href_match:
            continue
        href = urljoin(base_url, unescape(href_match.group(1)))
        if not _is_official_url(href):
            continue
        title_match = re.search(r"Advertisement\s+No\.[^<]+", item, flags=re.IGNORECASE)
        title = _clean_html(title_match.group(0) if title_match else item)
        links.append((title, href))
    return list(dict.fromkeys(links))


def _parse_date(value: str) -> str:
    return datetime.strptime(value, "%d-%m-%Y").date().isoformat()


def _deadline_dates(text: str) -> list[str]:
    section = re.search(
        r"CLOSING DATE.*?(?:DATE FOR DETERMINING|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    source = section.group(0) if section else text
    dates = re.findall(_DATE_RE, source)
    return [_parse_date(value) for value in dates]


def _first_match(pattern: str, text: str, *, flags: int = re.IGNORECASE) -> str:
    match = re.search(pattern, text, flags)
    return re.sub(r"\s+", " ", match.group(1)).strip(" .") if match else ""


def _vacancy_count(text: str) -> int | None:
    value = _first_match(
        r"((?:\d[\d,]*|one|two|three|four|five|six|seven|eight|nine|ten))"
        r"\s+vacanc(?:y|ies)",
        text,
    ).lower()
    if not value:
        return None
    if value in _NUMBER_WORDS:
        return _NUMBER_WORDS[value]
    return int(value.replace(",", "")) if value.isdigit() else None


def _post_title(text: str) -> str:
    for pattern in (
        r"for the post of\s+(.+?)(?=,\s+(?:Ministry|Department|Directorate)\b|"
        r"\s+in\s+|\s+under\s+|\s+at\s+|\s+of\s+the\s+post\b|"
        r"\.\s+RESERVATION POSITION)",
        r"post of\s+(.+?)(?=\s+in\s+|\s+under\s+|\s+at\s+)",
    ):
        value = _first_match(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if value:
            return value
    return text[:160].strip(" .")


def _employer(text: str) -> str:
    return _first_match(
        r"(?:\s+in\s+|,\s+)((?:Ministry|Department|Directorate).+?)(?=\.\s+RESERVATION POSITION|"
        r"\s+RESERVATION POSITION|\s+PAY SCALE:|\s+AGE:|"
        r"\s+ESSENTIAL QUALIFICATIONS:)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _headquarters(text: str) -> str:
    return _first_match(
        r"HEADQUARTERS:\s*(.+?)(?=\s+ANY OTHER CONDITIONS:|\s+PROBATION:|"
        r"\s+ESSENTIAL QUALIFICATIONS:|\s+AGE:)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _education_level(text: str) -> str | None:
    lowered = text.lower()
    if re.search(r"\b(ph\.d|phd|doctorate)\b", lowered):
        return "PhD"
    if re.search(r"\b(post[- ]graduate|postgraduate|master(?:'s)? degree)\b", lowered):
        return "PG"
    if re.search(r"\b(degree|bachelor|graduate|graduation)\b", lowered):
        return "UG"
    if re.search(r"\b(diploma|iti|polytechnic)\b", lowered):
        return "iti_diploma"
    if re.search(r"\b(class 10|10th|sslc|matric)\b", lowered):
        return "class_10"
    if re.search(r"\b(class 12|12th|puc|intermediate)\b", lowered):
        return "class_12"
    return None


def _experience_years(text: str) -> int | None:
    value = _first_match(
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
        r"\s+years?'?\s+(?:of\s+)?experience",
        text,
    ).lower()
    if value in _NUMBER_WORDS:
        return _NUMBER_WORDS[value]
    return int(value) if value.isdigit() else None


def _employment_type(text: str) -> str:
    lowered = text.lower()
    if "contract" in lowered:
        return "contract"
    if "permanent" in lowered:
        return "permanent"
    return "not stated"


def _posting_blocks(text: str) -> list[tuple[str, str]]:
    matches = list(_POST_RE.finditer(text))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks.append((match.group("vacancy").strip(), text[match.start() : end]))
    return blocks


def parse_advertisement(
    text: str,
    *,
    source_url: str,
    listing_title: str,
    source_content_hash: str | None = None,
    checked_on: date | None = None,
) -> list[dict]:
    """Convert one UPSC PDF's posting blocks into inactive Benefit rows."""
    checked_on = checked_on or date.today()
    advertisement = _first_match(r"ADVERTISEMENT NO\.\s*([0-9/ -]+)", text)
    advertisement = advertisement or listing_title
    start_dates = re.findall(rf"FROM\s+({_DATE_RE})", text, flags=re.IGNORECASE)
    closing_dates = _deadline_dates(text)
    start_date = _parse_date(start_dates[0]) if start_dates else None
    rows: list[dict] = []

    for vacancy_number, block in _posting_blocks(text):
        compact = re.sub(r"\s+", " ", block).strip()
        title = _post_title(compact)
        employer = _employer(compact)
        headquarters = _headquarters(compact)
        is_ladakh = "ADMINISTRATION OF UT OF LADAKH" in compact.upper()
        deadline = (
            closing_dates[1]
            if is_ladakh and len(closing_dates) > 1
            else closing_dates[0]
            if closing_dates
            else None
        )
        education = _education_level(compact)
        criteria = {
            "education_level": [education] if education else None,
            "min_experience_years": _experience_years(compact),
            "locations": [headquarters] if headquarters else None,
            "exclusions": [
                "Age limits, reservation relaxations, and equivalent qualifications "
                "must be checked in the official notification."
            ],
        }
        criteria = {key: value for key, value in criteria.items() if value not in (None, [])}
        count = _vacancy_count(compact)
        application_url = "https://upsconline.nic.in/ora/"
        row_id = slugify(f"upsc-{advertisement}-{vacancy_number}")
        rows.append(
            {
                "id": row_id,
                "domain": "job",
                "name": title,
                "state_code": None,
                "category": "Government Jobs",
                "description": f"{title} recruitment advertised by {employer or 'UPSC'}.",
                "eligibility_initial": criteria,
                "benefits_text": (
                    "Government recruitment post; pay scale and service conditions "
                    "are stated in the official notification."
                ),
                "documents_required": [],
                "application_process": (
                    f"Apply online at {application_url} before the closing date in "
                    "the official notification."
                ),
                "source_url": source_url,
                "source_title": f"{advertisement} · Vacancy No. {vacancy_number}",
                "source_document_url": source_url,
                "source_excerpt": compact[:4000],
                "source_content_hash": source_content_hash,
                "verification_status": "machine_structured",
                "last_verified_date": checked_on.isoformat(),
                "valid_from": start_date,
                "valid_until": deadline,
                "is_active": False,
                "job_metadata": {
                    "source_kind": "upsc_recruitment_advertisement",
                    "advertisement_number": advertisement,
                    "vacancy_number": vacancy_number,
                    "employer": employer or "UPSC recruitment notification",
                    "vacancy_count": count,
                    "employment_type": _employment_type(compact),
                    "published_at": start_date,
                    "application_deadline": deadline,
                    "headquarters": headquarters,
                    "application_url": application_url,
                },
                "automated_review": {
                    "reviewer": "official_source_parser",
                    "source": "UPSC recruitment advertisement PDF",
                    "review_required": True,
                    "review_fields": [
                        "title",
                        "vacancy_count",
                        "education",
                        "experience",
                        "age_and_reservation",
                        "deadline",
                        "documents",
                        "application_url",
                    ],
                },
            }
        )
    return rows


def _fetch(client: httpx.Client, url: str) -> bytes:
    if not _is_official_url(url):
        raise ValueError(f"Refusing non-UPSC URL: {url}")
    response = client.get(url)
    response.raise_for_status()
    if len(response.content) > MAX_PDF_BYTES:
        raise ValueError(f"Document exceeds the {MAX_PDF_BYTES} byte limit: {url}")
    return response.content


def _extract_text(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def run(
    *,
    index_url: str,
    output: Path,
    source_output: Path,
    limit: int,
    dry_run: bool,
    timeout: float,
) -> int:
    if not _is_official_url(index_url):
        raise SystemExit("The job importer only accepts an HTTPS UPSC index URL.")
    headers = {"User-Agent": "SahaayakJobImporter/0.1 (official-source review queue)"}
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        index_response = client.get(index_url)
        index_response.raise_for_status()
        links = extract_pdf_links(index_response.text, base_url=index_url)[:limit]
        if not links:
            raise SystemExit("No official UPSC PDF advertisements were found.")

        rows: list[dict] = []
        sources: list[dict] = []
        for listing_title, pdf_url in links:
            try:
                pdf_bytes = _fetch(client, pdf_url)
                PDF_CACHE.mkdir(parents=True, exist_ok=True)
                filename = Path(urlparse(pdf_url).path).name or "advertisement.pdf"
                (PDF_CACHE / filename).write_bytes(pdf_bytes)
                extracted_text = _extract_text(pdf_bytes)
                content_hash = hashlib.sha256(pdf_bytes).hexdigest()
                parsed = parse_advertisement(
                    extracted_text,
                    source_url=pdf_url,
                    listing_title=listing_title,
                    source_content_hash=content_hash,
                )
            except Exception as exc:
                raise SystemExit(f"Could not import {pdf_url}: {exc}") from exc
            rows.extend(parsed)
            sources.append(
                {
                    "source_id": slugify(f"upsc-{listing_title}-{filename}"),
                    "filename": filename,
                    "raw_text": extracted_text,
                    "source_hash": content_hash,
                    "source_url": pdf_url,
                    "source_title": listing_title,
                    "dataset": "upsc_recruitment",
                    "verification": "raw_machine_extracted",
                }
            )
            print(f"{listing_title}: extracted {len(parsed)} posting(s)")

    print(f"Total machine-structured job postings: {len(rows)}")
    if dry_run:
        for row in rows[:10]:
            count = row["job_metadata"].get("vacancy_count") or "?"
            print(
                f"- {row['name']} · {count} vacancy/vacancies · "
                f"deadline {row['valid_until'] or 'not stated'}"
            )
        return len(rows)

    _write_jsonl(output, rows)
    _write_jsonl(source_output, sources)
    print(f"Wrote inactive review queue to {output}")
    print(f"Wrote source text for RAG ingestion to {source_output}")
    print(f"Next: uv run python scripts/04_seed_db.py --file {output}")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-url", default=INDEX_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-output", type=Path, default=DEFAULT_SOURCE_OUTPUT)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(
        index_url=args.index_url,
        output=args.output,
        source_output=args.source_output,
        limit=max(1, min(args.limit, 20)),
        dry_run=args.dry_run,
        timeout=max(1.0, min(args.timeout, 120.0)),
    )


if __name__ == "__main__":
    main()
