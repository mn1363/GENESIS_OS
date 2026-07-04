from typing import List, Optional
from .base import BaseRepository


class TaskRepository(BaseRepository[dict]):
    """
    Simple in-memory task storage (Phase 4 scaffold).
    """

    def __init__(self):
        self._store = {}

    async def create(self, item: dict) -> dict:
        self._store[item["id"]] = item
        return item

    async def get(self, item_id: str) -> Optional[dict]:
        return self._store.get(item_id)

    async def list(self) -> List[dict]:
        return list(self._store.values())

    async def delete(self, item_id: str) -> bool:
        return self._store.pop(item_id, None) is not None