"""Unit tests for src/storage/di_wire.py."""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys

import pytest
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from src.config.settings import Settings
from src.core.di import DIContainer
from src.storage.database import DatabaseSessionManager
from src.storage.di_wire import (
    DB_SESSION_MANAGER,
    QDRANT_CLIENT,
    REDIS_CLIENT,
    _register_factories,
    dispose_storage,
    init_storage_schema,
    wire_storage,
)
from src.storage.event_repository import EventRepository
from src.storage.knowledge_graph import SQLAlchemyKnowledgeGraph
from src.storage.memory_repository import MemoryRepository
from src.storage.redis_client import RedisRepository, RedisShortTermMemory
from src.storage.repositories import RepositoryRegistry
from src.storage.sql_repository import SQLAlchemyRepository
from src.storage.task_repository import TaskRepository
from src.storage.vector_store import QdrantVectorMemory


def _in_memory_settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///:memory:")


def test_wire_storage_returns_a_populated_registry() -> None:
    container = DIContainer()

    registry = wire_storage(container, settings=_in_memory_settings())

    assert isinstance(registry, RepositoryRegistry)
    assert isinstance(registry.get("tasks"), TaskRepository)
    assert isinstance(registry.get("events"), EventRepository)
    assert isinstance(registry.get("memory"), MemoryRepository)
    assert isinstance(registry.get("sql_tasks"), SQLAlchemyRepository)
    assert isinstance(registry.get("sql_events"), SQLAlchemyRepository)
    assert isinstance(registry.get("redis_cache"), RedisRepository)
    assert isinstance(registry.get("short_term_memory"), RedisShortTermMemory)
    assert isinstance(registry.get("vector_memory"), QdrantVectorMemory)
    assert isinstance(registry.get("knowledge_graph"), SQLAlchemyKnowledgeGraph)


def test_wire_storage_is_built_through_the_container() -> None:
    """Every component must be reachable via container.build(), not just
    bundled inside the returned registry — that's what "wired through DI"
    means."""
    container = DIContainer()
    wire_storage(container, settings=_in_memory_settings())

    assert isinstance(container.build(DB_SESSION_MANAGER), DatabaseSessionManager)
    assert isinstance(container.build(REDIS_CLIENT), Redis)
    assert isinstance(container.build(QDRANT_CLIENT), AsyncQdrantClient)


def test_wire_storage_shares_one_session_manager() -> None:
    container = DIContainer()
    registry = wire_storage(container, settings=_in_memory_settings())

    session_manager = container.get_built(DB_SESSION_MANAGER)
    assert registry.get("sql_tasks")._sessions is session_manager  # noqa: SLF001
    assert registry.get("sql_events")._sessions is session_manager  # noqa: SLF001
    assert registry.get("knowledge_graph")._sessions is session_manager  # noqa: SLF001


async def test_init_storage_schema_creates_tables_and_repository_works() -> None:
    container = DIContainer()
    registry = wire_storage(container, settings=_in_memory_settings())
    await init_storage_schema(container)

    sql_tasks: SQLAlchemyRepository = registry.get("sql_tasks")
    await sql_tasks.create({"id": "t1"})

    assert await sql_tasks.get("t1") == {"id": "t1"}

    await dispose_storage(container)


async def test_dispose_storage_is_a_no_op_before_anything_is_built() -> None:
    container = DIContainer()
    _register_factories(container, _in_memory_settings())
    await dispose_storage(container)  # must not raise


@pytest.mark.parametrize("key", ["tasks", "events", "memory"])
def test_original_in_memory_repositories_are_unaffected(key: str) -> None:
    """Regression guard: Phase 4.2 must not change the Phase 4 scaffold's
    original three registry entries."""
    container = DIContainer()
    registry = wire_storage(container, settings=_in_memory_settings())

    repo = registry.get(key)
    assert hasattr(repo, "create")
    assert hasattr(repo, "get")
    assert hasattr(repo, "list")
    assert hasattr(repo, "delete")


def test_wire_storage_succeeds_even_when_sql_driver_is_unimportable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GEN-0025: wire_storage() must not require aiosqlite/asyncpg to be
    importable just to wire the container — in-memory repositories work
    independently of whether the SQL backend's driver is even installed.
    The driver is only required once a SQL repository is actually used
    (covered by test_database.py's own driver-blocking regression test).
    """

    class _Blocker(importlib.abc.MetaPathFinder):
        def find_spec(
            self, name: str, path: object, target: object = None
        ) -> importlib.machinery.ModuleSpec | None:
            if name == "aiosqlite" or name.startswith("aiosqlite."):
                raise ModuleNotFoundError(f"simulated: {name} not installed")
            return None

    for name in list(sys.modules):
        if name.startswith("aiosqlite"):
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(sys, "meta_path", [_Blocker(), *sys.meta_path])

    container = DIContainer()
    registry = wire_storage(container, settings=_in_memory_settings())  # must not raise

    assert isinstance(registry.get("tasks"), TaskRepository)
    assert isinstance(registry.get("sql_tasks"), SQLAlchemyRepository)
