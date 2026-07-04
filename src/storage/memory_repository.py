from typing import List, Optional
from .base import BaseRepository


class MemoryRepository(BaseRepository[dict]):
    """
    Simple key-value memory store.
    """

    def __init__(self):
        self._memory = {}

    async def create(self, item: dict) -> dict:
        self._memory[item["key"]] = item["value"]
        return item

    async def get(self, item_id: str) -> Optional[dict]:
        if item_id in self._memory:
            return {"key": item_id, "value": self._memory[item_id]}
        return None

    async def list(self) -> List[dict]:
        return [{"key": k, "value": v} for k, v in self._memory.items()]

    async def delete(self, item_id: str) -> bool:
        return self._memory.pop(item_id, None) is not None