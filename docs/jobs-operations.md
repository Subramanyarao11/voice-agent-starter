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
blocks and common dates, and stores the PDF in the ignored data/jobs/upsc/
directory. It does not scrape job aggregators, copy private portals, or call
an LLM.

The National Career Service has an official developer portal, but its API
requires a separately issued API key. It should be added as a second adapter
after the account terms, fields, and rate limits are confirmed.

## Run the importer

Preview the current official advertisements without writing the JSONL queue:

~~~bash
make jobs
~~~

Write the inactive review queue:

~~~bash
uv run --group pipeline python scripts/ingest_upsc_jobs.py
~~~

Load the rows into the local database:

~~~bash
uv run python scripts/04_seed_db.py --file data/structured/jobs.jsonl
~~~

The importer marks every row machine_structured and is_active=false.
Reviewers must confirm the post title, vacancy count, employer, qualifications,
reservation/age rules, documents, deadline, and application URL before
publishing it through the admin review flow.

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
