"""Unit tests for src/storage/sql_repository.py."""

from __future__ import annotations

import pytest
from src.storage.database import DatabaseSessionManager
from src.storage.sql_repository import SQLAlchemyRepository


@pytest.fixture
async def db() -> DatabaseSessionManager:
    manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")
    await manager.create_all()
    return manager


async def test_create_and_get_round_trips_item(db: DatabaseSessionManager) -> None:
    repo = SQLAlchemyRepository(db, "tasks")
    await repo.create({"id": "t1", "capability": "echo.say@v1"})

    fetched = await repo.get("t1")

    assert fetched == {"id": "t1", "capability": "echo.say@v1"}


async def test_get_returns_none_for_unknown_id(db: DatabaseSessionManager) -> None:
    repo = SQLAlchemyRepository(db, "tasks")
    assert await repo.get("missing") is None


async def test_create_upserts_existing_item(db: DatabaseSessionManager) -> None:
    repo = SQLAlchemyRepository(db, "tasks")
    await repo.create({"id": "t1", "state": "created"})
    await repo.create({"id": "t1", "state": "completed"})

    assert await repo.get("t1") == {"id": "t1", "state": "completed"}


async def test_list_returns_every_item_in_collection(db: DatabaseSessionManager) -> None:
    repo = SQLAlchemyRepository(db, "tasks")
    await repo.create({"id": "t1"})
    await repo.create({"id": "t2"})

    items = await repo.list()

    assert {i["id"] for i in items} == {"t1", "t2"}


async def test_collections_are_isolated_from_each_other(db: DatabaseSessionManager) -> None:
    tasks = SQLAlchemyRepository(db, "tasks")
    events = SQLAlchemyRepository(db, "events")
    await tasks.create({"id": "shared_id", "kind": "task"})
    await events.create({"id": "shared_id", "kind": "event"})

    assert await tasks.get("shared_id") == {"id": "shared_id", "kind": "task"}
    assert await events.get("shared_id") == {"id": "shared_id", "kind": "event"}
    assert len(await tasks.list()) == 1
    assert len(await events.list()) == 1


async def test_delete_removes_item(db: DatabaseSessionManager) -> None:
    repo = SQLAlchemyRepository(db, "tasks")
    await repo.create({"id": "t1"})

    assert await repo.delete("t1") is True
    assert await repo.get("t1") is None


async def test_delete_unknown_item_returns_false(db: DatabaseSessionManager) -> None:
    repo = SQLAlchemyRepository(db, "tasks")
    assert await repo.delete("missing") is False
