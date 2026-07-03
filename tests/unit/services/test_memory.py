"""Unit tests for src/services/memory/."""

from __future__ import annotations

import pytest
from src.services.memory.in_memory import (
    InMemoryKnowledgeGraph,
    InMemoryShortTermMemory,
    InMemoryVectorMemory,
)
from src.services.memory.service import MemoryService

pytestmark = pytest.mark.asyncio


async def test_short_term_memory_get_set_clear() -> None:
    mem = InMemoryShortTermMemory()
    await mem.set("session-1", "key", "value")
    assert await mem.get("session-1", "key") == "value"
    await mem.clear("session-1")
    assert await mem.get("session-1", "key") is None


async def test_vector_memory_search_orders_by_similarity() -> None:
    vec = InMemoryVectorMemory()
    await vec.upsert("a", [1.0, 0.0], {"label": "a"})
    await vec.upsert("b", [0.0, 1.0], {"label": "b"})
    await vec.upsert("c", [0.9, 0.1], {"label": "c"})

    results = await vec.search([1.0, 0.0], top_k=2)
    assert [r.id for r in results] == ["a", "c"]


async def test_vector_memory_delete() -> None:
    vec = InMemoryVectorMemory()
    await vec.upsert("a", [1.0, 0.0])
    await vec.delete("a")
    results = await vec.search([1.0, 0.0], top_k=5)
    assert results == []


async def test_knowledge_graph_neighbors() -> None:
    graph = InMemoryKnowledgeGraph()
    await graph.add_node("alice", labels=("person",))
    await graph.add_node("bob", labels=("person",))
    await graph.add_edge("alice", "bob", relation="knows")

    neighbors = await graph.neighbors("alice")
    assert [n.id for n in neighbors] == ["bob"]

    none_found = await graph.neighbors("alice", relation="dislikes")
    assert none_found == []


async def test_memory_service_capability_handlers_roundtrip() -> None:
    service = MemoryService()
    handlers = service.capability_handlers()

    await handlers["memory.short_term.set@v1"]({"session_id": "s1", "key": "k1", "value": "hello"})
    got = await handlers["memory.short_term.get@v1"]({"session_id": "s1", "key": "k1"})
    assert got == "hello"

    await handlers["memory.vector.upsert@v1"]({"id": "v1", "vector": [1.0, 0.0]})
    matches = await handlers["memory.vector.search@v1"]({"query_vector": [1.0, 0.0]})
    assert matches[0]["id"] == "v1"

    node = await handlers["memory.graph.add_node@v1"]({"id": "n1", "labels": ["thing"]})
    assert node["id"] == "n1"

    await handlers["memory.graph.add_edge@v1"](
        {"source": "n1", "target": "n2", "relation": "related_to"}
    )
    await handlers["memory.graph.add_node@v1"]({"id": "n2"})
    neighbors = await handlers["memory.graph.neighbors@v1"]({"node_id": "n1"})
    assert neighbors[0]["id"] == "n2"
