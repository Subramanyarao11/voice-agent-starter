"""Run the scheduled source-freshness worker.

Defaults to one scan so the command is safe for cron and local verification.
Compose runs it with ``--forever`` as a separate process from reminder
delivery.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from sahaayak_agent.bootstrap import ensure_reference_data
from sahaayak_api.workers.freshness_worker import FreshnessWorker
from sahaayak_common import configure_logging, init_db, settings


async def _run(args: argparse.Namespace) -> None:
    worker = FreshnessWorker(stale_days=args.stale_days)
    if args.forever:
        await worker.run_forever(interval_seconds=args.interval)
        return
    stats = worker.run_once()
    print(json.dumps(stats.as_metadata(), indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--forever",
        action="store_true",
        help="run continuously instead of one scan",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help=(
            "seconds between scans with --forever "
            f"(default: {settings.freshness_scan_interval_seconds})"
        ),
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=None,
        help=f"freshness threshold in days (default: {settings.freshness_stale_days})",
    )
    args = parser.parse_args()

    configure_logging()
    init_db()
    ensure_reference_data()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
