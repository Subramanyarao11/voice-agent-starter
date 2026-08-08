from __future__ import annotations

from datetime import date

from scripts.ingest_upsc_jobs import extract_pdf_links, parse_advertisement


def test_upsc_link_extractor_allows_only_official_pdf_links() -> None:
    html = """
    <ul>
      <li>Advertisement No.10 - 2026
        <a href="/sites/default/files/notice.pdf">PDF</a>
      </li>
      <li>Advertisement No.11 - 2026
        <a href="https://example.test/not-a-government-source.pdf">PDF</a>
      </li>
    </ul>
    """

    assert extract_pdf_links(html) == [
        (
            "Advertisement No.10 - 2026",
            "https://www.upsc.gov.in/sites/default/files/notice.pdf",
        )
    ]


def test_upsc_parser_creates_inactive_job_rows_with_deadline_and_criteria() -> None:
    text = """
ADVERTISEMENT NO. 10/2026
INVITES ONLINE RECRUITMENT APPLICATIONS
1. (Vacancy No. 26081001608) One vacancy for the post of Assistant Executive
Engineer (Civil) in Directorate General of Lighthouses.
PAY SCALE: Level-10 in the Pay Matrix.
HEADQUARTERS: Noida (UP)
ESSENTIAL QUALIFICATIONS: Degree in Civil Engineering.
EXPERIENCE: Two years' experience in construction.
2. (Vacancy No. 26081002608) Nine vacancies for the post of Assistant Engineer
in Ministry of Example.
HEADQUARTERS: Bengaluru
IMPORTANT
FROM 08-08-2026.
CLOSING DATE FOR SUBMISSION IS 1800 HRS ON 28-08-2026 AND 04-09-2026.
DATE FOR DETERMINING THE ELIGIBILITY
"""

    rows = parse_advertisement(
        text,
        source_url="https://www.upsc.gov.in/sites/default/files/notice.pdf",
        listing_title="Advertisement No.10 - 2026",
        source_content_hash="abc123",
        checked_on=date(2026, 8, 8),
    )

    assert len(rows) == 2
    assert rows[0]["domain"] == "job"
    assert rows[0]["is_active"] is False
    assert rows[0]["verification_status"] == "machine_structured"
    assert rows[0]["source_content_hash"] == "abc123"
    assert rows[0]["valid_from"] == "2026-08-08"
    assert rows[0]["valid_until"] == "2026-08-28"
    assert rows[0]["job_metadata"]["vacancy_count"] == 1
    assert rows[0]["job_metadata"]["application_deadline"] == "2026-08-28"
    assert rows[0]["eligibility_initial"]["education_level"] == ["UG"]
    assert rows[0]["eligibility_initial"]["min_experience_years"] == 2
    assert rows[0]["eligibility_initial"]["locations"] == ["Noida (UP)"]
