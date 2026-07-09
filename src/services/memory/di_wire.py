"""DI wiring for the Memory subsystem (Phase 6 Milestones 7-8, GEN-0025).

Integrates the production storage backends into `MemoryService` through
Dependency Injection only. Built entirely on existing architecture, with
nothing modified:

- `MemoryService` (`src/services/memory/service.py`) already accepts
  `short_term`/`vector`/`graph` constructor parameters, depending only on
  their respective Protocols (`ShortTermMemory`/`VectorMemory`/
  `KnowledgeGraph`) — this module is the first thing that actually passes
  it production instances instead of leaving them at their in-memory
  defaults.
- `src.storage.di_wire.wire_storage()` (Phase 4.2 / Milestone 6) already
  registers and can build `SHORT_TERM_MEMORY` (a `RedisShortTermMemory`),
  `VECTOR_MEMORY` (a `QdrantVectorMemory`), and `KNOWLEDGE_GRAPH` (a
  `SQLAlchemyKnowledgeGraph`) on a `DIContainer` — this module calls that
  existing public function rather than duplicating any storage-wiring
  logic.

Milestone 8 adds Redis (`SHORT_TERM_MEMORY`) and Qdrant (`VECTOR_MEMORY`)
to what Milestone 7 already wired for the Knowledge Graph; no change to
`MemoryService`, `src/storage/di_wire.py`, or any Protocol was needed for
either milestone.
"""

from __future__ import annotations

from src.config.settings import Settings
from src.core.di import DIContainer
from src.services.memory.service import MemoryService
from src.storage.di_wire import KNOWLEDGE_GRAPH, SHORT_TERM_MEMORY, VECTOR_MEMORY, wire_storage

MEMORY_SERVICE = "memory_service"


def wire_memory_service(container: DIContainer, settings: Settings | None = None) -> MemoryService:
    """Wire and build a `MemoryService` backed by the production Redis
    Short-Term Memory, Qdrant Vector Memory, and Knowledge Graph backends.

    Calls `wire_storage()` first to ensure all three are registered —
    safe to call even if the storage layer was already wired on
    `container`: `DIContainer.register_factory` overwrites any prior
    registration for the same name, and `DIContainer.build` caches built
    instances by name, so this never constructs a second
    `DatabaseSessionManager`, Redis client, Qdrant client, or any of the
    three memory backends.
    """
    wire_storage(container, settings)
    container.register_factory(
        MEMORY_SERVICE,
        lambda short_term_memory, vector_memory, knowledge_graph: MemoryService(
            short_term=short_term_memory, vector=vector_memory, graph=knowledge_graph
        ),
        dependencies=[SHORT_TERM_MEMORY, VECTOR_MEMORY, KNOWLEDGE_GRAPH],
    )
    memory_service: MemoryService = container.build(MEMORY_SERVICE)
    return memory_service
