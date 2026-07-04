"""Redis integration (Phase 4.2).

Two pieces, both built from the same `redis.asyncio.Redis` client:

- `RedisRepository` — a `BaseRepository[dict[str, Any]]` adapter, for
  parity with the SQL adapter where a cache-tier, non-durable store is
  preferable to SQLite/PostgreSQL.
- `RedisShortTermMemory` — a production implementation of
  `src.services.memory.interfaces.ShortTermMemory` (GEN-0005), the
  Protocol Phase 3 defined and explicitly left with only an in-memory
  reference implementation. Redis — not SQL — is the natural backend here:
  `ShortTermMemory` is ephemeral and session-scoped by definition, which is
  exactly what Redis with a TTL is for; this also matches
  `KERNEL_ARCHITECTURE_PROPOSAL.md` §5's original call for Redis as
  infrastructure, not just SQL.
"""

from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from src.storage.base import BaseRepository

_DEFAULT_SESSION_TTL_SECONDS = 3600


class RedisRepository(BaseRepository[dict[str, Any]]):
    """`BaseRepository[dict[str, Any]]` backed by a Redis hash.

    `collection` becomes the Redis key `storage:{collection}`, with each
    item stored as a JSON-encoded field keyed by its `"id"`.
    """

    def __init__(self, redis_client: Redis, collection: str) -> None:
        self._redis = redis_client
        self._key = f"storage:{collection}"

    async def create(self, item: dict[str, Any]) -> dict[str, Any]:
        await self._redis.hset(self._key, item["id"], json.dumps(item))
        return item

    async def get(self, item_id: str) -> dict[str, Any] | None:
        raw = await self._redis.hget(self._key, item_id)
        return json.loads(raw) if raw is not None else None

    async def list(self) -> list[dict[str, Any]]:
        values = await self._redis.hvals(self._key)
        return [json.loads(v) for v in values]

    async def delete(self, item_id: str) -> bool:
        removed = await self._redis.hdel(self._key, item_id)
        return bool(removed)


class RedisShortTermMemory:
    """Production `ShortTermMemory` (GEN-0005), backed by Redis.

    Implements `src.services.memory.interfaces.ShortTermMemory` structurally
    (that Protocol is `@runtime_checkable`) — callers depend on the
    Protocol, never on this class directly, so `MemoryService`
    (`src/services/memory/service.py`) can be pointed at either this or
    `InMemoryShortTermMemory` with no code change.
    """

    def __init__(
        self, redis_client: Redis, ttl_seconds: int = _DEFAULT_SESSION_TTL_SECONDS
    ) -> None:
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"stm:{session_id}"

    async def get(self, session_id: str, key: str) -> Any | None:
        raw = await self._redis.hget(self._key(session_id), key)
        return json.loads(raw) if raw is not None else None

    async def set(self, session_id: str, key: str, value: Any) -> None:
        redis_key = self._key(session_id)
        await self._redis.hset(redis_key, key, json.dumps(value))
        await self._redis.expire(redis_key, self._ttl_seconds)

    async def clear(self, session_id: str) -> None:
        await self._redis.delete(self._key(session_id))
