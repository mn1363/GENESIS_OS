"""Unit tests for the Phase 4 in-memory scaffold repositories.

These repositories (`TaskRepository`, `EventRepository`,
`MemoryRepository`, `RepositoryRegistry`) had no test coverage before
Phase 4.2 — added here alongside the new SQL/Redis/Qdrant backends they
share a contract with.
"""

from __future__ import annotations

import pytest
from src.storage.event_repository import EventRepository
from src.storage.memory_repository import MemoryRepository
from src.storage.repositories import RepositoryRegistry
from src.storage.task_repository import TaskRepository


async def test_task_repository_create_and_get() -> None:
    repo = TaskRepository()
    await repo.create({"id": "t1", "capability": "echo.say@v1"})

    fetched = await repo.get("t1")

    assert fetched == {"id": "t1", "capability": "echo.say@v1"}


async def test_task_repository_get_missing_returns_none() -> None:
    repo = TaskRepository()
    assert await repo.get("missing") is None


async def test_task_repository_create_upserts() -> None:
    repo = TaskRepository()
    await repo.create({"id": "t1", "state": "created"})
    await repo.create({"id": "t1", "state": "completed"})

    assert await repo.get("t1") == {"id": "t1", "state": "completed"}


async def test_task_repository_list_returns_every_item() -> None:
    repo = TaskRepository()
    await repo.create({"id": "t1"})
    await repo.create({"id": "t2"})

    items = await repo.list()

    assert {i["id"] for i in items} == {"t1", "t2"}


async def test_task_repository_delete() -> None:
    repo = TaskRepository()
    await repo.create({"id": "t1"})

    assert await repo.delete("t1") is True
    assert await repo.get("t1") is None
    assert await repo.delete("t1") is False


async def test_event_repository_create_and_list_preserves_order() -> None:
    repo = EventRepository()
    await repo.create({"id": "e1"})
    await repo.create({"id": "e2"})

    assert [e["id"] for e in await repo.list()] == ["e1", "e2"]


async def test_event_repository_get_and_delete() -> None:
    repo = EventRepository()
    await repo.create({"id": "e1"})

    assert await repo.get("e1") == {"id": "e1"}
    assert await repo.delete("e1") is True
    assert await repo.get("e1") is None


async def test_memory_repository_create_get_list_delete() -> None:
    repo = MemoryRepository()
    await repo.create({"key": "greeting", "value": "hi"})

    assert await repo.get("greeting") == {"key": "greeting", "value": "hi"}
    assert await repo.list() == [{"key": "greeting", "value": "hi"}]
    assert await repo.delete("greeting") is True
    assert await repo.get("greeting") is None


def test_repository_registry_register_and_get() -> None:
    registry = RepositoryRegistry()
    repo = TaskRepository()

    registry.register("tasks", repo)

    assert registry.get("tasks") is repo


def test_repository_registry_get_missing_raises_key_error() -> None:
    registry = RepositoryRegistry()
    with pytest.raises(KeyError):
        registry.get("missing")
