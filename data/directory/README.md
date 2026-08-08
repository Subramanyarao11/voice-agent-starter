# Department directory import format

`scripts/16_import_department_directory.py` accepts a JSON list (or an object
with an `entries` list). It is deliberately an import-and-review workflow:
every incoming row is reset to `pending` and inactive. A reviewer must inspect
the official source in the admin console before routing can use it.

Each entry should contain at least:

```json
{
  "state_code": "KA",
  "district_name": "Bengaluru Urban",
  "service_domain": "citizen_support",
  "department_name": "District Social Welfare Office",
  "source_name": "Bengaluru Urban district portal",
  "source_url": "https://bengaluruurban.nic.in/",
  "source_last_verified": "2026-08-09T00:00:00+05:30"
}
```

For a state-wide department record, leave `district_name`, `pincode`, and
`pincode_prefix` empty. The importer accepts both state-wide and district
records; the runtime only uses a state-wide row when there is no more specific
approved district or postal match.

Use `pincode` for an exact six-digit postal match or `pincode_prefix` for a
source that only attests to a postal range. The routing layer prefers exact
pincode, then prefix, then exact district, and otherwise keeps the existing
state/domain fallback. It never uses an unapproved or stale row.

Recommended official source inputs are:

- [India Post pincode list](https://www.indiapost.gov.in/rti/pincodelist) for
  postal code and post-office geography.
- [Karnataka district portal](https://karnataka.s3waas.gov.in/) and the relevant
  district portal directory for public department/help-centre records.
- [Integrated Government Online Directory](https://igod.gov.in/) when an
  organisation record is the authoritative source for a department.

## Automated India.gov snapshot

The first supported public-source adapter uses the structured endpoint behind
India.gov's contact directory. It fetches state/UT departments, directorates,
and district portals without inventing phone numbers or pincode ownership:

```bash
uv run python scripts/21_ingest_india_gov_directory.py --state-code KA
uv run python scripts/16_import_department_directory.py \
  --file data/directory/snapshots/india-gov-*.json
```

Use `--all-states` for the complete India.gov state/UT catalogue. The snapshot
is ignored by Git because it is regenerated from the official source. Every
row remains `pending` and inactive after import. A repeated import preserves
approval when the source record's stable hash is unchanged; a changed title or
portal URL sends the row back to review.

India.gov gives us a useful official department/district portal directory, not
a universal department-to-pincode table. The routing layer therefore treats a
pincode as a candidate postal hint and only uses an exact pincode/prefix when a
separately reviewed source attests it. Until then, approved district records
are the strongest safe match and all other cases use the labelled state/domain
fallback.

Do not copy an office phone number or individual officer contact into this
directory without verifying that it is still published by the source. Keep the
source URL and verification timestamp with every row.
