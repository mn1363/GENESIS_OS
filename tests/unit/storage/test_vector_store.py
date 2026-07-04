"""Unit tests for src/storage/vector_store.py.

Uses Qdrant's built-in local in-process mode (`location=":memory:"`) —
no live Qdrant server needed, and no test double: this is the real
`qdrant_client` code path, just without a network server behind it.
"""

from __future__ import annotations

from qdrant_client import AsyncQdrantClient
from src.services.memory.interfaces import VectorMemory
from src.storage.vector_store import QdrantVectorMemory


def _make_store(collection_name: str = "test_collection") -> QdrantVectorMemory:
    client = AsyncQdrantClient(location=":memory:")
    return QdrantVectorMemory(client, collection_name=collection_name)


async def test_upsert_and_search_finds_the_exact_match() -> None:
    store = _make_store()
    await store.upsert("v1", [1.0, 0.0, 0.0], metadata={"label": "x-axis"})

    results = await store.search([1.0, 0.0, 0.0], top_k=1)

    assert len(results) == 1
    assert results[0].id == "v1"
    assert results[0].metadata == {"label": "x-axis"}
    assert results[0].score == 1.0


async def test_search_ranks_by_similarity() -> None:
    store = _make_store()
    await store.upsert("close", [1.0, 0.0, 0.0])
    await store.upsert("far", [0.0, 1.0, 0.0])

    results = await store.search([0.9, 0.1, 0.0], top_k=2)

    assert [r.id for r in results] == ["close", "far"]


async def test_search_respects_top_k() -> None:
    store = _make_store()
    for i in range(5):
        await store.upsert(f"v{i}", [float(i), 0.0, 0.0])

    results = await store.search([0.0, 0.0, 0.0], top_k=2)

    assert len(results) == 2


async def test_delete_removes_vector() -> None:
    store = _make_store()
    await store.upsert("v1", [1.0, 0.0, 0.0])

    await store.delete("v1")
    results = await store.search([1.0, 0.0, 0.0], top_k=5)

    assert results == []


async def test_upsert_overwrites_existing_id() -> None:
    store = _make_store()
    await store.upsert("v1", [1.0, 0.0, 0.0], metadata={"version": 1})
    await store.upsert("v1", [1.0, 0.0, 0.0], metadata={"version": 2})

    results = await store.search([1.0, 0.0, 0.0], top_k=5)

    assert len(results) == 1
    assert results[0].metadata == {"version": 2}


def test_qdrant_vector_memory_satisfies_protocol() -> None:
    store = _make_store()
    assert isinstance(store, VectorMemory)
