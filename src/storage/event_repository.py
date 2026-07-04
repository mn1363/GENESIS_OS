"""In-memory event store (Phase 4 baseline).

Unchanged contract from the Phase 4 scaffold — see `sql_repository.py` for
the durable SQLite/PostgreSQL-backed alternative added in Phase 4.2, which
implements the same `BaseRepository[dict[str, Any]]` contract.
"""

from __future__ import annotations

from typing import Any

from src.storage.base import BaseRepository


class EventRepository(BaseRepository[dict[str, Any]]):
    """In-memory event store (Phase 4 baseline)."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    async def create(self, item: dict[str, Any]) -> dict[str, Any]:
        self._events.append(item)
        return item

    async def get(self, item_id: str) -> dict[str, Any] | None:
        return next((e for e in self._events if e.get("id") == item_id), None)

    async def list(self) -> list[dict[str, Any]]:
        return self._events

    async def delete(self, item_id: str) -> bool:
        before = len(self._events)
        self._events = [e for e in self._events if e.get("id") != item_id]
        return len(self._events) < before
