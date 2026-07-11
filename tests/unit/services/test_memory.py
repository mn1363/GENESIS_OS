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


# ---- health_check() production validation (Phase 6 Milestone 10) --------------------


async def test_health_check_is_true_with_default_in_memory_backends() -> None:
    assert await MemoryService().health_check() is True


async def test_health_check_does_not_mutate_short_term_or_graph_state() -> None:
    """The probe keys/node_id must not leak into real backend state."""
    service = MemoryService()
    await service.health_check()

    assert await service.short_term.get("__health_check__", "__health_check__") is None
    assert await service.graph.neighbors("__health_check__") == []


async def test_health_check_returns_false_when_short_term_backend_fails() -> None:
    class _BrokenShortTerm:
        async def get(self, session_id: str, key: str) -> None:
            raise ConnectionError("simulated Redis outage")

        async def set(self, session_id: str, key: str, value: object) -> None:
            raise ConnectionError("simulated Redis outage")

        async def clear(self, session_id: str) -> None:
            raise ConnectionError("simulated Redis outage")

    service = MemoryService(short_term=_BrokenShortTerm())
    assert await service.health_check() is False


async def test_health_check_returns_false_when_graph_backend_fails() -> None:
    class _BrokenGraph:
        async def add_node(
            self, id: str, labels: tuple[str, ...] = (), properties: dict[str, object] | None = None
        ) -> object:
            raise ConnectionError("simulated database outage")

        async def add_edge(
            self,
            source: str,
            target: str,
            relation: str,
            properties: dict[str, object] | None = None,
        ) -> object:
            raise ConnectionError("simulated database outage")

        async def neighbors(self, node_id: str, relation: str | None = None) -> list[object]:
            raise ConnectionError("simulated database outage")

    service = MemoryService(graph=_BrokenGraph())  # type: ignore[arg-type]
    assert await service.health_check() is False


async def test_health_check_does_not_touch_vector_backend_at_all() -> None:
    """health_check() must never call vector's upsert/search/delete --
    doing so would risk creating a wrong-dimension Qdrant collection or
    raising for a not-yet-created one. Confirmed here by a vector double
    that fails any call."""

    class _ExplodingVector:
        async def upsert(
            self, id: str, vector: list[float], metadata: dict[str, object] | None = None
        ) -> None:
            raise AssertionError("health_check() must never call vector.upsert")

        async def search(self, query_vector: list[float], top_k: int = 5) -> list[object]:
            raise AssertionError("health_check() must never call vector.search")

        async def delete(self, id: str) -> None:
            raise AssertionError("health_check() must never call vector.delete")

    service = MemoryService(vector=_ExplodingVector())  # type: ignore[arg-type]
    assert await service.health_check() is True
