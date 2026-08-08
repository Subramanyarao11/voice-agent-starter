"""Scheduled source-freshness worker contracts."""

from datetime import UTC, date, datetime, timedelta

from sahaayak_api.workers.freshness_worker import FreshnessWorker
from sahaayak_common import Benefit, SourceFreshnessAlert, TelemetryEvent, session_scope
from sahaayak_contracts import Domain, VerificationStatus


def test_worker_persists_deduplicated_alerts_and_aggregate_telemetry() -> None:
    benefit_id = "scheduled-freshness-worker-test"
    now = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    with session_scope() as db:
        db.add(
            Benefit(
                id=benefit_id,
                domain=Domain.SCHEME,
                name="Scheduled freshness test benefit",
                state_code="KA",
                source_url="https://example.test/scheduled-freshness",
                source_document_url="https://example.test/scheduled-freshness",
                source_title="Official test source",
                last_verified_date=date(2026, 1, 1),
                verification_status=VerificationStatus.HUMAN_VERIFIED,
                verified_by="test-reviewer",
                verified_at=now,
                is_active=True,
            )
        )

    try:
        worker = FreshnessWorker(stale_days=90)
        first = worker.run_once(now=now)
        second = worker.run_once(now=now + timedelta(minutes=1))

        assert first.open_alerts >= 1
        assert second.open_alerts >= 1
        with session_scope() as db:
            alerts = db.query(SourceFreshnessAlert).filter_by(benefit_id=benefit_id).all()
            assert len(alerts) == 1
            assert alerts[0].status == "open"
            telemetry = db.query(TelemetryEvent).filter(
                TelemetryEvent.route == "worker/freshness"
            ).all()
            assert telemetry
            assert telemetry[-1].safe_metadata["stale_days"] == 90
    finally:
        with session_scope() as db:
            for alert in db.query(SourceFreshnessAlert).filter_by(benefit_id=benefit_id).all():
                db.delete(alert)
            row = db.get(Benefit, benefit_id)
            if row is not None:
                db.delete(row)
