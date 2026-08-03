"""Run the notification worker.

Defaults to a single batch so it is safe to run by hand and safe to schedule
from cron. ``--forever`` is the deployment mode, used by the Compose service.

A dry run reports what would be claimed without sending anything, which is the
right first command after enabling a channel.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime

from sahaayak_api.workers.notification_worker import (
    BATCH_SIZE,
    NotificationWorker,
    claim_due_reminders,
    pending_delivery_count,
)
from sahaayak_common import configure_logging, init_db, session_scope


async def _run(args: argparse.Namespace) -> None:
    worker = NotificationWorker(batch_size=args.batch_size)

    if args.forever:
        await worker.run_forever(interval_seconds=args.interval)
        return

    stats = await worker.run_once()
    with session_scope() as db:
        pending = pending_delivery_count(db)

    print(
        json.dumps(
            {**stats.as_metadata(), "reasons": stats.reasons, "awaiting_reports": pending},
            indent=2,
        )
    )


def _dry_run(args: argparse.Namespace) -> None:
    """Report what is due without claiming or sending it."""
    now = datetime.now(UTC)
    with session_scope() as db:
        # Claim into an aborted transaction: the rows are read exactly as the
        # worker would see them, and the lease is rolled back.
        due = claim_due_reminders(db, now=now, limit=args.batch_size)
        summary = [
            {"reminder_id": row.id, "channel": row.channel, "due_at": row.due_at.isoformat()}
            for row in due
        ]
        db.rollback()
    print(json.dumps({"would_claim": len(summary), "reminders": summary}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--forever", action="store_true", help="run continuously instead of one batch"
    )
    parser.add_argument(
        "--interval", type=float, default=30.0, help="seconds between batches with --forever"
    )
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what is due without sending; run this first after enabling a channel",
    )
    args = parser.parse_args()

    configure_logging()
    init_db()

    if args.dry_run:
        _dry_run(args)
        return
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
