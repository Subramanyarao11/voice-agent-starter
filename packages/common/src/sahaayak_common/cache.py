"""Cache with a Redis backend and an in-process fallback.

The fallback exists so the conversation loop runs on a laptop without Docker,
but it is not merely a convenience: synthesised speech is expensive and
credit-limited, so a process-local cache still avoids re-paying for the same
canned prompt during development.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

import structlog

from sahaayak_common.settings import settings

log = structlog.get_logger(__name__)


class Cache(ABC):
    @abstractmethod
    async def get(self, key: str) -> bytes | None: ...

    @abstractmethod
    async def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...


class InMemoryCache(Cache):
    """Process-local cache. Entries do not survive a restart, by design."""

    def __init__(self, max_entries: int = 512) -> None:
        self._store: dict[str, tuple[bytes, float | None]] = {}
        self._max_entries = max_entries

    async def get(self, key: str) -> bytes | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and expires_at < time.monotonic():
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None:
        if len(self._store) >= self._max_entries:
            # Cheap eviction: drop the oldest insertion. Good enough for a
            # cache whose worst case is one extra synthesis call.
            self._store.pop(next(iter(self._store)), None)
        expires_at = time.monotonic() + ttl_seconds if ttl_seconds else None
        self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class RedisCache(Cache):
    def __init__(self, url: str) -> None:
        from redis.asyncio import Redis

        self._client = Redis.from_url(url, decode_responses=False)

    async def get(self, key: str) -> bytes | None:
        return await self._client.get(key)

    async def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None:
        await self._client.set(key, value, ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:
            return False


_cache: Cache | None = None


async def get_cache() -> Cache:
    """Return the shared cache, degrading to memory if Redis is unreachable.

    The Redis check happens once. A cache that flaps between backends mid-run
    would be harder to reason about than one that picked a lane at startup.
    """
    global _cache
    if _cache is not None:
        return _cache

    if settings.redis_url:
        candidate = RedisCache(settings.redis_url)
        if await candidate.ping():
            log.info("cache_backend_selected", backend="redis")
            _cache = candidate
            return _cache
        log.warning(
            "redis_unreachable_using_memory_cache",
            redis_url=settings.redis_url,
            impact="cached audio will not survive a restart",
        )

    log.info("cache_backend_selected", backend="memory")
    _cache = InMemoryCache()
    return _cache


def reset_cache() -> None:
    """Drop the cached backend selection. Used by tests."""
    global _cache
    _cache = None
