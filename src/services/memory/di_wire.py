"""DI wiring for the Memory subsystem (Phase 6 Milestone 7, GEN-0025).

Integrates the production Knowledge Graph (`src.storage.knowledge_graph`,
Phase 6 Milestone 6) into `MemoryService` through Dependency Injection
only. Built entirely on existing architecture, with nothing modified:

- `MemoryService` (`src/services/memory/service.py`) already accepts a
  `graph: KnowledgeGraph | None` constructor parameter, depending only on
  the `KnowledgeGraph` Protocol — this module is the first thing that
  actually passes it a production instance instead of leaving it to
  default to `InMemoryKnowledgeGraph`.
- `src.storage.di_wire.wire_storage()` (Phase 4.2 / Milestone 6) already
  registers and can build `KNOWLEDGE_GRAPH` (a `SQLAlchemyKnowledgeGraph`)
  on a `DIContainer` — this module calls that existing public function
  rather than duplicating any storage-wiring logic.

Deliberately out of scope for this milestone (see the Knowledge Memory
Integration requirements): `short_term`/`vector` are left at
`MemoryService`'s own in-memory defaults — wiring `RedisShortTermMemory`
or `QdrantVectorMemory` in is a separate integration, not part of
"integrate the existing Knowledge Graph into the Memory subsystem."
"""

from __future__ import annotations

from src.config.settings import Settings
from src.core.di import DIContainer
from src.services.memory.service import MemoryService
from src.storage.di_wire import KNOWLEDGE_GRAPH, wire_storage

MEMORY_SERVICE = "memory_service"


def wire_memory_service(container: DIContainer, settings: Settings | None = None) -> MemoryService:
    """Wire and build a `MemoryService` backed by the production Knowledge
    Graph.

    Calls `wire_storage()` first to ensure `KNOWLEDGE_GRAPH` is
    registered — safe to call even if the storage layer was already wired
    on `container`: `DIContainer.register_factory` overwrites any prior
    registration for the same name, and `DIContainer.build` caches built
    instances by name, so this never constructs a second
    `DatabaseSessionManager` or a second Knowledge Graph.
    """
    wire_storage(container, settings)
    container.register_factory(
        MEMORY_SERVICE,
        lambda knowledge_graph: MemoryService(graph=knowledge_graph),
        dependencies=[KNOWLEDGE_GRAPH],
    )
    memory_service: MemoryService = container.build(MEMORY_SERVICE)
    return memory_service
