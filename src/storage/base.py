"""Base repository contract for all storage backends.

Phase 4 scaffold, extended: this contract is unchanged from the Phase 4
scaffold (`create`/`get`/`list`/`delete` on a dict-shaped item keyed by
`"id"`) — every concrete adapter added in Phase 4.2 (`sql_repository.py`,
`redis_client.py`) implements this same `BaseRepository[dict]` contract so
callers can swap backends without changing call sites.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseRepository[T](ABC):
    """Base repository contract for all storage backends."""

    @abstractmethod
    async def create(self, item: T) -> T:
        """Persist a new item and return it."""
        raise NotImplementedError

    @abstractmethod
    async def get(self, item_id: str) -> T | None:
        """Return the item with `item_id`, or None if it doesn't exist."""
        raise NotImplementedError

    @abstractmethod
    async def list(self) -> list[T]:
        """Return every persisted item."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, item_id: str) -> bool:
        """Remove the item with `item_id`. Returns True if it existed."""
        raise NotImplementedError
