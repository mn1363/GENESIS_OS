"""Hybrid Memory — Short-Term, Vector (Qdrant abstraction), Knowledge Graph.

Phase 3: interfaces + in-memory reference implementations. Phase 6
Milestone 6 added a production Knowledge Graph backend
(`src.storage.knowledge_graph.SQLAlchemyKnowledgeGraph`); Milestone 7
(`di_wire.py`) wires it into `MemoryService` via Dependency Injection.
Production `ShortTermMemory`/`VectorMemory` backends
(`src.storage.redis_client`/`src.storage.vector_store`) exist too but are
not yet wired into `MemoryService` — a separate integration.
"""

from src.services.memory.di_wire import MEMORY_SERVICE, wire_memory_service
from src.services.memory.in_memory import (
    InMemoryKnowledgeGraph,
    InMemoryShortTermMemory,
    InMemoryVectorMemory,
)
from src.services.memory.interfaces import (
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    ShortTermMemory,
    VectorMatch,
    VectorMemory,
)
from src.services.memory.service import MemoryService

__all__ = [
    "ShortTermMemory",
    "VectorMemory",
    "VectorMatch",
    "KnowledgeGraph",
    "GraphNode",
    "GraphEdge",
    "InMemoryShortTermMemory",
    "InMemoryVectorMemory",
    "InMemoryKnowledgeGraph",
    "MemoryService",
    "wire_memory_service",
    "MEMORY_SERVICE",
]
