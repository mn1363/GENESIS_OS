"""Unit tests for src/storage/base.py.

Exercises the abstract method bodies directly (via a minimal concrete
subclass calling `super()`) so the contract's own `NotImplementedError`
raises are covered, not just its concrete implementers.
"""

from __future__ import annotations

from typing import Any

import pytest
from src.storage.base import BaseRepository


class _StubRepository(BaseRepository[dict[str, Any]]):
    async def create(self, item: dict[str, Any]) -> dict[str, Any]:
        return await super().create(item)  # type: ignore[safe-super]

    async def get(self, item_id: str) -> dict[str, Any] | None:
        return await super().get(item_id)  # type: ignore[safe-super]

    async def list(self) -> list[dict[str, Any]]:
        return await super().list()  # type: ignore[safe-super]

    async def delete(self, item_id: str) -> bool:
        return await super().delete(item_id)  # type: ignore[safe-super]


def test_base_repository_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        BaseRepository()  # type: ignore[abstract]


async def test_create_body_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        await _StubRepository().create({"id": "x"})


async def test_get_body_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        await _StubRepository().get("x")


async def test_list_body_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        await _StubRepository().list()


async def test_delete_body_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        await _StubRepository().delete("x")
