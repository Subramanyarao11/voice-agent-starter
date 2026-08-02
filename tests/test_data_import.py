"""Verification-state and source-change rules for the ingestion boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from importlib import import_module

import pytest

from sahaayak_common import Benefit, session_scope
from sahaayak_contracts import VerificationStatus

importer = import_module("scripts.04_seed_db")


@pytest.fixture(autouse=True)
def clean_import_rows():
    yield
    with session_scope() as db:
        for row in db.query(Benefit).filter(Benefit.id.startswith("import-")).all():
            db.delete(row)


def benefit_row(benefit_id: str, source_hash: str, **overrides) -> dict:
    row = {
        "id": benefit_id,
        "domain": "scholarship",
        "name": "Test scholarship",
        "description": "A test benefit.",
        "eligibility_initial": {"age_min": 18},
        "source_title": "Test source",
        "source_document_url": "https://example.com/test",
        "source_content_hash": source_hash,
        "verification_status": "machine_structured",
        "is_active": False,
    }
    row.update(overrides)
    return row


def test_import_is_idempotent_by_benefit_id(seeded):
    row = benefit_row("import-idempotent", "hash-a")
    with session_scope() as db:
        assert importer.import_benefit(db, importer.build_benefit(row)) == "seeded"
        assert importer.import_benefit(db, importer.build_benefit(row)) == "seeded"

    with session_scope() as db:
        rows = list(db.query(Benefit).filter_by(id="import-idempotent").all())
        assert len(rows) == 1
        assert rows[0].source_content_hash == "hash-a"


def test_changed_source_requires_review_and_deactivates_row(seeded):
    first = benefit_row("import-changed", "hash-a")
    second = benefit_row("import-changed", "hash-b")

    with session_scope() as db:
        assert importer.import_benefit(db, importer.build_benefit(first)) == "seeded"
        assert importer.import_benefit(db, importer.build_benefit(second)) == "changed_source"
        row = db.get(Benefit, "import-changed")
        assert row is not None
        assert row.verification_status is VerificationStatus.NEEDS_REVIEW
        assert row.is_active is False
        assert row.source_content_hash == "hash-b"


def test_machine_import_cannot_replace_human_verified_row(seeded):
    verified = benefit_row(
        "import-protected",
        "hash-a",
        verification_status="human_verified",
        verified_by="reviewer-1",
        verified_at=datetime.now(UTC).isoformat(),
        is_active=True,
    )
    replacement = benefit_row("import-protected", "hash-b", name="New extraction")

    with session_scope() as db:
        assert importer.import_benefit(db, importer.build_benefit(verified)) == "seeded"
        assert (
            importer.import_benefit(db, importer.build_benefit(replacement))
            == "protected_verified"
        )
        row = db.get(Benefit, "import-protected")
        assert row is not None
        assert row.name == "Test scholarship"
        assert row.verification_status is VerificationStatus.HUMAN_VERIFIED
        assert row.source_content_hash == "hash-a"
        assert row.is_active is True
