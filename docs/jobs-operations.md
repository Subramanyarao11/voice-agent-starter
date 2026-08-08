# Government jobs operations

Sahaayak treats a job posting as a time-bounded Benefit row with
domain=job. The existing deterministic matcher is reused for education,
experience, location, and other explicitly structured fields. A posting is
never made active merely because a scraper found it.

## Current source adapter

The first adapter is restricted to the official UPSC recruitment-advertisement
index:

https://www.upsc.gov.in/recruitment/recruitment-advertisement

The importer follows only HTTPS PDF links on upsc.gov.in, extracts posting
blocks and common dates, stores the PDF in the ignored data/jobs/upsc/
directory, and writes one full-text source record per notification for the
OpenAI-hosted RAG sync. It does not scrape job aggregators, copy private
portals, or call an LLM.

The Karnataka Public Service Commission adapter follows the official
notification index:

https://kpsc.kar.nic.in/notification.html

It accepts only HTTPS PDFs on `kpsc.kar.nic.in`, filters obvious result,
cancellation, tender, and non-recruitment notices, and tolerates the legacy
site's malformed response header through a constrained `curl` fallback. It
does not treat the mixed notification page as a job feed; each accepted PDF is
still an inactive review row.

The National Career Service has an official developer portal, but machine API
access requires a separately issued API key and current account terms. The NCS
adapter is implemented at `scripts/ingest_ncs_jobs.py`; it refuses an absent or
non-allowlisted API URL, accepts only records with an explicit Government
marker, and also supports an exported JSON response for a no-network test.
It intentionally does not scrape the NCS browser UI. Confirm the current API
fields and rate limits with NCS before enabling it.

## Run the importer

Preview the current official advertisements without writing the JSONL queue:

~~~bash
make jobs
~~~

Write the inactive review queue:

~~~bash
uv run --group pipeline python scripts/ingest_upsc_jobs.py
~~~

This writes both `data/structured/jobs.jsonl` (21 structured matcher/review
rows) and `data/structured/job_sources.jsonl` (3 full notification texts for
RAG). The two outputs have different purposes and should not be conflated.

The first sync completed against the existing persistent OpenAI Vector Store:
the remote corpus contains 2,066 myScheme documents plus 3 UPSC source
documents. Re-running the sync is manifest-driven and does not re-upload those
documents unless their source hash changes.

After reviewing the dry-run and confirming the budget delta, include the job
notifications in the same persistent Vector Store:

~~~bash
uv run python scripts/07_sync_openai_vector_store.py --dataset upsc_recruitment --dry-run
uv run python scripts/07_sync_openai_vector_store.py --dataset state_government_jobs --dry-run
uv run python scripts/07_sync_openai_vector_store.py --dataset ncs_government_jobs --dry-run
uv run python scripts/07_sync_openai_vector_store.py --dataset all
~~~

The sync command reads only source-text JSONL outputs; it never silently
downloads a new source or calls the paid structuring model. The current remote
store contains the previously synced 2,066 myScheme documents and 3 UPSC
documents. KPSC and NCS documents are not added to that remote store merely by
running a dry-run; review the source output and confirm the budget before a
real sync.

Load the rows into the local database:

~~~bash
uv run python scripts/04_seed_db.py --file data/structured/jobs.jsonl
~~~

The importer marks every row machine_structured and is_active=false.
Reviewers must confirm the post title, vacancy count, employer, qualifications,
reservation/age rules, documents, deadline, and application URL before
publishing it through the admin review flow.

Preview and write the Karnataka state queue:

~~~bash
make jobs-state
uv run --group pipeline python scripts/ingest_state_jobs.py --state-code KA
~~~

This writes `data/structured/state_jobs.jsonl` and
`data/structured/state_job_sources.jsonl`. The source text is the notification
PDF text, not a generated summary, and is eligible for RAG provenance only
after the source has been reviewed according to the same publication policy.

When NCS developer access is available, configure the endpoint in the server
environment and run:

~~~bash
NCS_API_URL=https://portal.api.nationalcareers.service.gov.in/... \\
  NCS_API_KEY=... \\
  uv run --group pipeline python scripts/ingest_ncs_jobs.py --dry-run
uv run --group pipeline python scripts/ingest_ncs_jobs.py
~~~

The NCS output is `data/structured/ncs_jobs.jsonl` plus
`data/structured/ncs_job_sources.jsonl`; every row is inactive and
`machine_structured` until a reviewer verifies the original listing.

## Expiry behavior

valid_until is populated from the official notification when a closing date
is found. The matcher excludes postings whose valid_until has passed, even if
an old database row was accidentally left active. Refreshing the source does
not delete old rows; an operator should deactivate or retain them as historical
records according to the retention policy.

## Safety rules

- Show the official notification URL on every job result.
- Treat a missing deadline as “not stated”, never as an open-ended application.
- Do not infer reservation, age relaxation, fee exemption, or qualification
  equivalence from a job title.
- Do not accept payment or documents inside Sahaayak.
- Do not activate a job until an authorised reviewer has checked the source.
- Do not describe an expired or unverified posting as currently available.
