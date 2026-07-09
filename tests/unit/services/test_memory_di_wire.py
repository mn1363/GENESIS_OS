"""Unit tests for src/services/memory/di_wire.py."""

from __future__ import annotations

from src.config.settings import Settings
from src.core.di import DIContainer
from src.services.memory.di_wire import MEMORY_SERVICE, wire_memory_service
from src.services.memory.in_memory import InMemoryShortTermMemory, InMemoryVectorMemory
from src.services.memory.service import MemoryService
from src.storage.di_wire import (
    DB_SESSION_MANAGER,
    KNOWLEDGE_GRAPH,
    init_storage_schema,
    wire_storage,
)
from src.storage.knowledge_graph import SQLAlchemyKnowledgeGraph


def _in_memory_settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///:memory:")


def test_wire_memory_service_returns_a_memory_service() -> None:
    container = DIContainer()

    memory_service = wire_memory_service(container, settings=_in_memory_settings())

    assert isinstance(memory_service, MemoryService)


def test_wire_memory_service_uses_the_production_knowledge_graph() -> None:
    container = DIContainer()

    memory_service = wire_memory_service(container, settings=_in_memory_settings())

    assert isinstance(memory_service.graph, SQLAlchemyKnowledgeGraph)


def test_wire_memory_service_shares_the_container_built_knowledge_graph() -> None:
    """The MemoryService's graph must be the exact same instance the
    container built for KNOWLEDGE_GRAPH — not a second, independently
    constructed one."""
    container = DIContainer()

    memory_service = wire_memory_service(container, settings=_in_memory_settings())

    assert memory_service.graph is container.get_built(KNOWLEDGE_GRAPH)


def test_wire_memory_service_leaves_short_term_and_vector_at_in_memory_defaults() -> None:
    """Out of scope for this milestone: only the Knowledge Graph is wired
    to a production backend; short_term/vector stay MemoryService's own
    in-memory defaults."""
    container = DIContainer()

    memory_service = wire_memory_service(container, settings=_in_memory_settings())

    assert isinstance(memory_service.short_term, InMemoryShortTermMemory)
    assert isinstance(memory_service.vector, InMemoryVectorMemory)


def test_wire_memory_service_is_idempotent_with_prior_storage_wiring() -> None:
    """Calling wire_storage() first, then wire_memory_service(), must not
    construct a second DatabaseSessionManager or a second Knowledge Graph."""
    container = DIContainer()
    wire_storage(container, settings=_in_memory_settings())
    session_manager_before = container.get_built(DB_SESSION_MANAGER)
    knowledge_graph_before = container.get_built(KNOWLEDGE_GRAPH)

    memory_service = wire_memory_service(container, settings=_in_memory_settings())

    assert container.get_built(DB_SESSION_MANAGER) is session_manager_before
    assert container.get_built(KNOWLEDGE_GRAPH) is knowledge_graph_before
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
