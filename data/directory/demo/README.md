# Karnataka two-district directory demo pack

`ka-two-districts.json` is a small, source-attested snapshot for the demo flow:

- Bengaluru Urban: Deputy Commissioner office and Bhoomi/Land Records service
- Mysuru: Deputy Commissioner office and Regional Commissioner's office

The records are not seed data and are not activated automatically. They are
normal importer input and remain pending until an admin reviews the source
links, contact details, coverage basis, and freshness date in Admin →
Department directory.

Run:

```bash
uv run python scripts/16_import_department_directory.py \
  --file data/directory/demo/ka-two-districts.json
```

The source pages were checked on 2026-08-09. The working-hours value is
intentionally explicit that the official pages did not publish hours; this
prevents the demo from presenting an invented schedule as fact.
