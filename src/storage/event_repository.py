from typing import List, Optional
from .base import BaseRepository


class EventRepository(BaseRepository[dict]):
    """
    In-memory event store (Phase 4 baseline).
    """

    def __init__(self):
        self._events = []

    async def create(self, item: dict) -> dict:
        self._events.append(item)
        return item

    async def get(self, item_id: str) -> Optional[dict]:
        return next((e for e in self._events if e.get("id") == item_id), None)

    async def list(self) -> List[dict]:
        return self._events

    async def delete(self, item_id: str) -> bool:
        before = len(self._events)
        self._events = [e for e in self._events if e.get("id") != item_id]
        return len(self._events) < before