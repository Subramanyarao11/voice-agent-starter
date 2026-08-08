from __future__ import annotations

import importlib


def test_ncs_adapter_accepts_only_explicit_government_records() -> None:
    module = importlib.import_module("scripts.ingest_ncs_jobs")

    parsed = module.parse_job(
        {
            "id": "ncs-42",
            "is_government": True,
            "title": "Junior Assistant",
            "employer_name": "Department of Public Administration",
            "state": "Karnataka",
            "qualification": "Bachelor degree",
            "last_date": "28-08-2026",
            "source_url": "https://www.ncs.gov.in/job/42",
            "application_url": "https://www.ncs.gov.in/job/42/apply",
        }
    )

    assert parsed is not None
    row, source = parsed
    assert row["is_active"] is False
    assert row["verification_status"] == "machine_structured"
    assert row["state_code"] == "KA"
    assert row["valid_until"] == "2026-08-28"
    assert source["dataset"] == "ncs_government_jobs"

    assert module.parse_job({"title": "Private Developer", "is_government": False}) is None


def test_state_adapter_filters_mixed_official_notification_page() -> None:
    module = importlib.import_module("scripts.ingest_state_jobs")
    source = module.STATE_SOURCES["KA"]
    html = """
    <a href="/files/GP-2026-notification.pdf">319 posts notification</a>
    <a href="/files/GP-result.pdf">selection list result</a>
    <a href="https://example.com/not-official.pdf">recruitment notification</a>
    """

    links = module.extract_pdf_links(
        html,
        base_url=source.index_url,
        allowed_hosts=source.allowed_hosts,
    )

    assert links == [
        (
            "319 posts notification",
            "https://kpsc.kar.nic.in/files/GP-2026-notification.pdf",
        )
    ]

    row = module.parse_notification(
        "The last date for submission is 28-08-2026. 319 posts.",
        source_url=links[0][1],
        listing_title=links[0][0],
        source=source,
        source_content_hash="pdf-hash",
    )
    assert row["is_active"] is False
    assert row["verification_status"] == "machine_structured"
    assert row["job_metadata"]["vacancy_count"] == 319
    assert row["valid_until"] == "2026-08-28"


def test_state_adapter_uses_constrained_curl_fallback_for_bad_legacy_headers(
    monkeypatch,
) -> None:
    module = importlib.import_module("scripts.ingest_state_jobs")
    source = module.STATE_SOURCES["KA"]

    class BrokenClient:
        def get(self, _url: str):
            raise module.httpx.RemoteProtocolError("malformed header")

    monkeypatch.setattr(
        module,
        "_curl_fetch",
        lambda _url, *, timeout: b"<html>official page</html>",
    )

    assert module._fetch_index(BrokenClient(), source, timeout=5.0) == (
        "<html>official page</html>"
    )
