"""Scan active/human-verified sources and persist deduplicated freshness alerts.

Usage:
    uv run python scripts/15_scan_source_freshness.py
    uv run python scripts/15_scan_source_freshness.py --stale-days 60
"""

from __future__ import annotations

import argparse

from sahaayak_agent.bootstrap import ensure_reference_data
from sahaayak_api.benefit_freshness import scan_source_freshness
from sahaayak_common import init_db, session_scope


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stale-days", type=int, default=90)
    args = parser.parse_args()
    if args.stale_days < 1 or args.stale_days > 730:
        raise SystemExit("--stale-days must be between 1 and 730")

    init_db()
    ensure_reference_data()
    with session_scope() as db:
        alerts = scan_source_freshness(db, stale_days=args.stale_days)
        print(
            f"Freshness scan complete: {len(alerts)} open/acknowledged alerts "
            f"at a {args.stale_days}-day threshold."
        )
        for alert in alerts[:20]:
            print(f"  [{alert.severity}] {alert.dataset} · {alert.message}")
        if len(alerts) > 20:
            print(f"  ... and {len(alerts) - 20} more")


if __name__ == "__main__":
    main()
