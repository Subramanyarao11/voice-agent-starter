"""Scheduled source-freshness scanning for the operations console.

The API exposes a manual scan for reviewers, but source freshness must not
depend on somebody opening the admin page. This worker is deliberately small:
it only evaluates the existing publication scope, persists deduplicated alerts,
and emits aggregate telemetry. It never publishes a benefit or changes review
status.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

from sahaayak_api.benefit_freshness import scan_source_freshness
from sahaayak_api.telemetry import record_telemetry
from sahaayak_common import get_logger, session_scope, settings

log = get_logger(__name__)

MIN_INTERVAL_SECONDS = 60
MAX_STALE_DAYS = 730


@dataclass(frozen=True, slots=True)
class FreshnessRunStats:
    scanned_at: datetime
    stale_days: int
    open_alerts: int
    acknowledged_alerts: int
    critical_alerts: int
    alert_types: dict[str, int]

    def as_metadata(self) -> dict[str, int | str]:
        return {
            "stale_days": self.stale_days,
            "open_alerts": self.open_alerts,
            "acknowledged_alerts": self.acknowledged_alerts,
            "critical_alerts": self.critical_alerts,
            "alert_types": ",".join(
                f"{key}:{value}" for key, value in sorted(self.alert_types.items())
            ),
        }


class FreshnessWorker:
    """Run one or more source-freshness scans outside the API process."""

    def __init__(self, *, stale_days: int | None = None) -> None:
        configured = settings.freshness_stale_days if stale_days is None else stale_days
        self.stale_days = max(1, min(int(configured), MAX_STALE_DAYS))

    def run_once(self, *, now: datetime | None = None) -> FreshnessRunStats:
        moment = now or datetime.now(UTC)
        with session_scope() as db:
            alerts = scan_source_freshness(
                db,
                stale_days=self.stale_days,
                now=moment,
            )
            # Materialize primitive aggregates before the transaction closes;
            # SQLAlchemy expires ORM rows on commit and the worker must not
            # retain detached alert objects between runs.
            statuses = Counter(alert.status for alert in alerts)
            severities = Counter(alert.severity for alert in alerts)
            alert_types = Counter(alert.alert_type for alert in alerts)
        stats = FreshnessRunStats(
            scanned_at=moment,
            stale_days=self.stale_days,
            open_alerts=statuses.get("open", 0),
            acknowledged_alerts=statuses.get("acknowledged", 0),
            critical_alerts=severities.get("critical", 0),
            alert_types=dict(alert_types),
        )
        record_telemetry(
            event_type="system",
            route="worker/freshness",
            method="WORKER",
            surface="system",
            outcome="completed",
            safe_metadata=stats.as_metadata(),
        )
        log.info("freshness_worker_scan", **stats.as_metadata())
        return stats

    async def run_forever(
        self, *, interval_seconds: float | None = None
    ) -> None:  # pragma: no cover
        configured = (
            settings.freshness_scan_interval_seconds
            if interval_seconds is None
            else interval_seconds
        )
        interval = max(MIN_INTERVAL_SECONDS, float(configured))
        log.info(
            "freshness_worker_started",
            interval_seconds=interval,
            stale_days=self.stale_days,
        )
        while True:
            try:
                self.run_once()
            except Exception as exc:
                # A transient database failure must not end the scheduler. The
                # next run retries the scan and the admin page remains the
                # manual recovery path.
                log.error(
                    "freshness_worker_scan_failed",
                    error=str(exc),
                    error_type=exc.__class__.__name__,
                    exc_info=True,
                )
            await asyncio.sleep(interval)


__all__ = ["FreshnessRunStats", "FreshnessWorker"]
