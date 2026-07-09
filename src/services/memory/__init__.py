"""Hybrid Memory — Short-Term, Vector (Qdrant abstraction), Knowledge Graph.

Phase 3: interfaces + in-memory reference implementations. Phase 6
Milestones 6-8 added production backends
(`src.storage.knowledge_graph.SQLAlchemyKnowledgeGraph`,
`src.storage.redis_client.RedisShortTermMemory`,
`src.storage.vector_store.QdrantVectorMemory`) and wired all three into
`MemoryService` via Dependency Injection (`di_wire.py`).
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
