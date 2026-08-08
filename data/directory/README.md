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

Do not copy an office phone number or individual officer contact into this
directory without verifying that it is still published by the source. Keep the
source URL and verification timestamp with every row.
