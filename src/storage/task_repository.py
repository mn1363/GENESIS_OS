"""In-memory task storage (Phase 4 baseline).

Unchanged contract from the Phase 4 scaffold — see `sql_repository.py` for
the durable SQLite/PostgreSQL-backed alternative added in Phase 4.2, which
implements the same `BaseRepository[dict[str, Any]]` contract.
"""

from __future__ import annotations

from typing import Any

from src.storage.base import BaseRepository


class TaskRepository(BaseRepository[dict[str, Any]]):
    """Simple in-memory task storage (Phase 4 scaffold)."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    async def create(self, item: dict[str, Any]) -> dict[str, Any]:
        self._store[item["id"]] = item
        return item

    async def get(self, item_id: str) -> dict[str, Any] | None:
        return self._store.get(item_id)

    async def list(self) -> list[dict[str, Any]]:
        return list(self._store.values())

    async def delete(self, item_id: str) -> bool:
        return self._store.pop(item_id, None) is not None
