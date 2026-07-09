"""Unit tests for src/services/memory/di_wire.py."""

from __future__ import annotations

from fakeredis.aioredis import FakeRedis
from qdrant_client import AsyncQdrantClient
from src.config.settings import Settings
from src.core.di import DIContainer
from src.services.memory.di_wire import MEMORY_SERVICE, wire_memory_service
from src.services.memory.service import MemoryService
from src.storage.di_wire import (
    DB_SESSION_MANAGER,
    KNOWLEDGE_GRAPH,
    SHORT_TERM_MEMORY,
    VECTOR_MEMORY,
    init_storage_schema,
    wire_storage,
)
from src.storage.knowledge_graph import SQLAlchemyKnowledgeGraph
from src.storage.redis_client import RedisShortTermMemory
from src.storage.vector_store import QdrantVectorMemory


def _in_memory_settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///:memory:")


def test_wire_memory_service_returns_a_memory_service() -> None:
    container = DIContainer()

    memory_service = wire_memory_service(container, settings=_in_memory_settings())

    assert isinstance(memory_service, MemoryService)


def test_wire_memory_service_uses_all_three_production_backends() -> None:
    container = DIContainer()

    memory_service = wire_memory_service(container, settings=_in_memory_settings())

    assert isinstance(memory_service.short_term, RedisShortTermMemory)
    assert isinstance(memory_service.vector, QdrantVectorMemory)
    assert isinstance(memory_service.graph, SQLAlchemyKnowledgeGraph)


def test_wire_memory_service_shares_the_container_built_instances() -> None:
    """The MemoryService's backends must be the exact same instances the
    container built — not second, independently constructed ones."""
    container = DIContainer()

    memory_service = wire_memory_service(container, settings=_in_memory_settings())

    assert memory_service.short_term is container.get_built(SHORT_TERM_MEMORY)
    assert memory_service.vector is container.get_built(VECTOR_MEMORY)
    assert memory_service.graph is container.get_built(KNOWLEDGE_GRAPH)


def test_wire_memory_service_is_idempotent_with_prior_storage_wiring() -> None:
    """Calling wire_storage() first, then wire_memory_service(), must not
    construct a second DatabaseSessionManager, Redis client, Qdrant
    client, or any of the three memory backends."""
    container = DIContainer()
    wire_storage(container, settings=_in_memory_settings())
    session_manager_before = container.get_built(DB_SESSION_MANAGER)
    short_term_before = container.get_built(SHORT_TERM_MEMORY)
    vector_before = container.get_built(VECTOR_MEMORY)
    knowledge_graph_before = container.get_built(KNOWLEDGE_GRAPH)

    memory_service = wire_memory_service(container, settings=_in_memory_settings())

    assert container.get_built(DB_SESSION_MANAGER) is session_manager_before
    assert memory_service.short_term is short_term_before
    assert memory_service.vector is vector_before
    assert memory_service.graph is knowledge_graph_before


async def test_wired_memory_service_graph_capability_handlers_work_end_to_end() -> None:
    """Not a placeholder: the wired MemoryService's graph capability
    handlers actually persist through the production Knowledge Graph."""
    container = DIContainer()
    memory_service = wire_memory_service(container, settings=_in_memory_settings())
    await init_storage_schema(container)

    await memory_service.graph_add_node({"id": "alice", "labels": ["person"]})
    await memory_service.graph_add_node({"id": "bob", "labels": ["person"]})
    await memory_service.graph_add_edge({"source": "alice", "target": "bob", "relation": "knows"})

    neighbors = await memory_service.graph_neighbors({"node_id": "alice"})

    assert neighbors == [{"id": "bob", "labels": ("person",), "properties": {}}]


def test_memory_service_registered_under_expected_container_name() -> None:
    container = DIContainer()
    memory_service = wire_memory_service(container, settings=_in_memory_settings())
    assert container.get_built(MEMORY_SERVICE) is memory_service


# ---- MemoryService + production Redis/Qdrant backends, capability handlers ----------
#
# wire_memory_service() builds Redis/Qdrant clients from Settings.redis_url/
# qdrant_host/qdrant_port, which point at real network addresses -- no live
# servers are available in this environment (see Phase_4_Implementation_Report.md's
# testing-strategy note), so these tests construct MemoryService directly with
# RedisShortTermMemory/QdrantVectorMemory backed by fakeredis / Qdrant's local
# ":memory:" mode, exactly like tests/unit/storage/test_redis_client.py and
# test_vector_store.py do for those classes on their own. This proves
# MemoryService's existing capability handlers work end-to-end against the real
# production backend classes Milestone 8 wires in -- not a placeholder or a mock
# of MemoryService's own behavior.


async def test_short_term_capability_handlers_work_with_production_redis_backend() -> None:
    memory_service = MemoryService(short_term=RedisShortTermMemory(FakeRedis()))

    await memory_service.short_term_set({"session_id": "s1", "key": "topic", "value": "genesis os"})
    result = await memory_service.short_term_get({"session_id": "s1", "key": "topic"})

    assert result == "genesis os"


async def test_vector_capability_handlers_work_with_production_qdrant_backend() -> None:
    client = AsyncQdrantClient(location=":memory:")
    memory_service = MemoryService(vector=QdrantVectorMemory(client))

    await memory_service.vector_upsert({"id": "v1", "vector": [1.0, 0.0], "metadata": {"x": 1}})
    results = await memory_service.vector_search({"query_vector": [1.0, 0.0], "top_k": 1})

    assert results == [{"id": "v1", "score": 1.0, "metadata": {"x": 1}}]
