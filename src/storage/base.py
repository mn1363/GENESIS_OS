from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """
    Base repository contract for all storage backends.
    """

    @abstractmethod
    async def create(self, item: T) -> T:
        raise NotImplementedError

    @abstractmethod
    async def get(self, item_id: str) -> Optional[T]:
        raise NotImplementedError

    @abstractmethod
    async def list(self) -> List[T]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, item_id: str) -> bool:
        raise NotImplementedError