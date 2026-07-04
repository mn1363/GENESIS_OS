"""Simple key-value memory store (Phase 4 baseline).

Unchanged contract from the Phase 4 scaffold. Not to be confused with
`src.services.memory` (GEN-0005 Hybrid Memory) — this is a generic
key/value `BaseRepository[dict[str, Any]]` adapter; see `redis_client.py`
for the Phase 4.2 `RedisShortTermMemory`, which implements the actual
`ShortTermMemory` Protocol from `src.services.memory.interfaces`.
"""

from __future__ import annotations

from typing import Any

from src.storage.base import BaseRepository


class MemoryRepository(BaseRepository[dict[str, Any]]):
    """Simple key-value memory store."""

    def __init__(self) -> None:
        self._memory: dict[str, Any] = {}

    async def create(self, item: dict[str, Any]) -> dict[str, Any]:
        self._memory[item["key"]] = item["value"]
        return item

    async def get(self, item_id: str) -> dict[str, Any] | None:
        if item_id in self._memory:
            return {"key": item_id, "value": self._memory[item_id]}
        return None

    async def list(self) -> list[dict[str, Any]]:
        return [{"key": k, "value": v} for k, v in self._memory.items()]

    async def delete(self, item_id: str) -> bool:
        return self._memory.pop(item_id, None) is not None
