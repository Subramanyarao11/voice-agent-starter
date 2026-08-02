"""Exercise the shared Redis limiter from two independent client instances."""

from __future__ import annotations

import argparse
import asyncio
import uuid

from sahaayak_api.rate_limit import _RedisSlidingWindow
from sahaayak_common import settings


async def main(limit: int, attempts: int) -> None:
    if not settings.redis_url:
        raise SystemExit("REDIS_URL is required; start Redis before this smoke test")
    from redis.asyncio import Redis

    clients = [Redis.from_url(settings.redis_url, decode_responses=True) for _ in range(2)]
    limiters = [_RedisSlidingWindow(client) for client in clients]
    key = f"sahaayak:smoke:{uuid.uuid4().hex}"
    try:
        decisions = await asyncio.gather(
            *(
                limiters[index % 2].consume(key, limit=limit, window_seconds=60)
                for index in range(attempts)
            )
        )
        allowed = sum(decision.allowed for decision in decisions)
        print({"instances": 2, "attempts": attempts, "limit": limit, "allowed": allowed})
        if allowed != limit:
            raise SystemExit(f"distributed limiter allowed {allowed} requests; expected {limit}")
    finally:
        for client in clients:
            await client.delete(key)
            await client.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--attempts", type=int, default=20)
    args = parser.parse_args()
    asyncio.run(main(max(1, args.limit), max(1, args.attempts)))
