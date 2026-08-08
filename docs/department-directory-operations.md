# Department directory operations

Sahaayak uses public government directory data to make human handoffs more
useful while keeping the final route explainable.

## Current source boundary

The first adapter is the official structured contact-directory endpoint used by
[India.gov](https://www.india.gov.in/directory/contact-directory). It supplies:

- state and union-territory department records;
- directorate/commissionerate records; and
- district portal records.

The record keeps the India.gov directory page as its provenance URL and keeps a
linked department or district portal as the public destination URL. The source
does not establish that every scheme belongs to the listed office, and it does
not provide a complete department-to-pincode jurisdiction map. Those facts are
why the import is a review queue rather than an automatic publish operation.

## Fetch and import

Fetch one state while developing:

```bash
uv run python scripts/21_ingest_india_gov_directory.py --state-code KA
```

Fetch all state/UT records:

```bash
uv run python scripts/21_ingest_india_gov_directory.py --all-states
```

Then import the generated snapshot:

```bash
uv run python scripts/16_import_department_directory.py \
  --file data/directory/snapshots/india-gov-<timestamp>.json
```

The importer is idempotent by `entry_key`. New rows are pending/inactive. A
new fetch updates the source verification timestamp. If its stable source hash
changes, the row is reset to pending/inactive so the reviewer can inspect the
new source. An unchanged approved row keeps its approval.

## Two-district demo pack

For a deterministic end-to-end demo, import the curated official snapshot for
Bengaluru Urban and Mysuru:

```bash
make directory-demo
```

It contains four enriched records: two offices/services in each district,
with address, phone, email, public portal, source record, exact pincode,
working-hours disclosure, supported-language evidence, and a coverage basis.
The source pages were checked on 2026-08-09. The rows remain pending until a
reviewer confirms them. This is an importer fixture, not a runtime seed or an
eligibility dataset.

## Runtime safety rules

Routing only considers rows that are all of the following:

1. approved by a reviewer or administrator;
2. active;
3. within the configured directory freshness window; and
4. matched by the caller's state plus an explicitly stated district or
   attested pincode/prefix.

If no row satisfies those rules, the operator sees a state/domain fallback and
must confirm the destination. The application never treats an India.gov row as
final eligibility evidence for a benefit.

## Review and monitoring

The admin Directory view exposes source counts, state/UT coverage, approved
versus pending rows, stale rows, enriched contact fields, and the current
content revision. Reviewers can edit a row, inspect immutable history, and
send an edit back to pending. Every import, edit, approval, deactivation, and
rollback appends a version and an audit event.

The regular freshness scan also creates a deduplicated
`department_directory` alert for an active approved row whose source is
missing, outside the configured freshness window, or past `valid_until`.

Rollback is administrator-only. It restores the selected snapshot as a new
version but deliberately leaves the row pending/inactive; the administrator
must re-check freshness and approve it again before callers can use it.

The five automated demo scenarios are covered in
`tests/test_department_directory.py`: exact pincode, pincode prefix, exact
district, stale-source fallback, and pending/unapproved fallback.

Reviewers should open both the India.gov source URL and the linked public portal,
confirm that the organization is still active, check the district/office
scope, and record the decision in Admin → Directory. A stale or changed source
must be refreshed before approval.

## Future pincode adapter

India Post and the Local Government Directory are appropriate official inputs
for postal/local-body geography, but they should be stored as geography
evidence rather than copied into a department route. A future adapter can
join those records to a department only after a source explicitly attests the
service jurisdiction. Until that join is reviewed, district routing remains
the safer behavior.
