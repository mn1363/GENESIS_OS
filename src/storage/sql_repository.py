"""SQLAlchemy-backed repository — the SQLite/PostgreSQL adapter (Phase 4.2).

Implements `BaseRepository[dict[str, Any]]` — the same contract as the
Phase 4 in-memory `TaskRepository`/`EventRepository`/`MemoryRepository` —
so it's a drop-in durable replacement wherever those are used. Works
unmodified against SQLite (`aiosqlite`) or PostgreSQL (`asyncpg`); the
dialect is entirely determined by the `DatabaseSessionManager` it's given,
itself built from `Settings.database_url`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.engine import CursorResult

from src.storage.base import BaseRepository
from src.storage.database import DatabaseSessionManager
from src.storage.models import StorageRecord


class SQLAlchemyRepository(BaseRepository[dict[str, Any]]):
    """Durable `BaseRepository[dict[str, Any]]` backed by SQLite or PostgreSQL.

    `collection` namespaces rows in the shared `storage_records` table
    (e.g. `"tasks"`, `"events"`) — one instance per collection, matching
    how the Phase 4 scaffold gave each entity its own repository instance.
    """

    def __init__(self, db_session_manager: DatabaseSessionManager, collection: str) -> None:
        self._sessions = db_session_manager
        self._collection = collection

    async def create(self, item: dict[str, Any]) -> dict[str, Any]:
        """Persist `item`, upserting by id — matches the in-memory
        repositories' `create()`, which is dict-assignment (i.e. upsert),
        not insert-only."""
        async with self._sessions.session() as session:
            record = await session.get(StorageRecord, (self._collection, item["id"]))
            if record is None:
                session.add(
                    StorageRecord(collection=self._collection, item_id=item["id"], data=item)
                )
            else:
                record.data = item
        return item

    async def get(self, item_id: str) -> dict[str, Any] | None:
        async with self._sessions.session() as session:
            record = await session.get(StorageRecord, (self._collection, item_id))
            return dict(record.data) if record is not None else None

    async def list(self) -> list[dict[str, Any]]:
        async with self._sessions.session() as session:
            result = await session.execute(
                select(StorageRecord).where(StorageRecord.collection == self._collection)
            )
            return [dict(record.data) for record in result.scalars().all()]

    async def delete(self, item_id: str) -> bool:
        async with self._sessions.session() as session:
            result = await session.execute(
                sa_delete(StorageRecord).where(
                    StorageRecord.collection == self._collection,
                    StorageRecord.item_id == item_id,
                )
            )
            assert isinstance(result, CursorResult)
            return result.rowcount > 0
