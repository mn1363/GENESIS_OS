"""Unit tests for src/storage/redis_client.py.

Uses `fakeredis` (in-memory, no live Redis server needed) since a real
Redis instance isn't available in this environment — see
`Phase_4_Implementation_Report.md` for the testing-strategy note.
"""

from __future__ import annotations

from fakeredis.aioredis import FakeRedis
from src.storage.redis_client import RedisRepository, RedisShortTermMemory


async def _fake_redis() -> FakeRedis:
    return FakeRedis()


async def test_redis_repository_create_and_get() -> None:
    repo = RedisRepository(await _fake_redis(), "cache")
    await repo.create({"id": "c1", "value": "hi"})

    assert await repo.get("c1") == {"id": "c1", "value": "hi"}


async def test_redis_repository_get_missing_returns_none() -> None:
    repo = RedisRepository(await _fake_redis(), "cache")
    assert await repo.get("missing") is None


async def test_redis_repository_create_upserts() -> None:
    repo = RedisRepository(await _fake_redis(), "cache")
    await repo.create({"id": "c1", "value": "first"})
    await repo.create({"id": "c1", "value": "second"})

    assert await repo.get("c1") == {"id": "c1", "value": "second"}


async def test_redis_repository_list_returns_every_item() -> None:
    repo = RedisRepository(await _fake_redis(), "cache")
    await repo.create({"id": "c1"})
    await repo.create({"id": "c2"})

    items = await repo.list()

    assert {i["id"] for i in items} == {"c1", "c2"}


async def test_redis_repository_collections_are_isolated() -> None:
    client = await _fake_redis()
    cache = RedisRepository(client, "cache")
    other = RedisRepository(client, "other")
    await cache.create({"id": "x"})

    assert await other.list() == []


async def test_redis_repository_delete() -> None:
    repo = RedisRepository(await _fake_redis(), "cache")
    await repo.create({"id": "c1"})

    assert await repo.delete("c1") is True
    assert await repo.get("c1") is None
    assert await repo.delete("c1") is False


async def test_short_term_memory_set_and_get() -> None:
    memory = RedisShortTermMemory(await _fake_redis())
    await memory.set("session-1", "topic", "storage layer")

    assert await memory.get("session-1", "topic") == "storage layer"


async def test_short_term_memory_get_missing_returns_none() -> None:
    memory = RedisShortTermMemory(await _fake_redis())
    assert await memory.get("session-1", "missing") is None


async def test_short_term_memory_sessions_are_isolated() -> None:
    memory = RedisShortTermMemory(await _fake_redis())
    await memory.set("session-1", "key", "a")
    await memory.set("session-2", "key", "b")

    assert await memory.get("session-1", "key") == "a"
    assert await memory.get("session-2", "key") == "b"


async def test_short_term_memory_clear_removes_whole_session() -> None:
    memory = RedisShortTermMemory(await _fake_redis())
    await memory.set("session-1", "a", 1)
    await memory.set("session-1", "b", 2)

    await memory.clear("session-1")

    assert await memory.get("session-1", "a") is None
    assert await memory.get("session-1", "b") is None


async def test_short_term_memory_sets_ttl_on_write() -> None:
    client = await _fake_redis()
    memory = RedisShortTermMemory(client, ttl_seconds=60)
    await memory.set("session-1", "key", "value")

    ttl = await client.ttl("stm:session-1")

    assert 0 < ttl <= 60
