"""Hybrid Memory — interfaces only.

Phase 3 architecture decision: "Implement the architecture only for
Short-Term Memory, Vector Memory (Qdrant abstraction), Knowledge Graph
abstraction. No production storage implementation yet." These Protocols
are the contract; `in_memory.py` provides reference/test-double
implementations (explicitly not production-grade) so the contracts are
exercisable in tests. A real Qdrant-backed VectorMemory, a
PostgreSQL/SQLite-backed ShortTermMemory, and a real graph-database-backed
KnowledgeGraph are later-phase work — see Phase_3_Implementation_Report.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ShortTermMemory(Protocol):
    """Ephemeral, session-scoped key/value memory (GEN-0005 Memory Architecture)."""

    async def get(self, session_id: str, key: str) -> Any | None: ...

    async def set(self, session_id: str, key: str, value: Any) -> None: ...

    async def clear(self, session_id: str) -> None: ...


@dataclass(frozen=True)
class VectorMatch:
    id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class VectorMemory(Protocol):
    """Semantic/vector memory abstraction (GEN-0026 Vector Memory Architecture).

    This Protocol is the Qdrant abstraction referred to in the Phase 3
    decision — production code should depend on this interface, never on
    a concrete Qdrant client directly, so a non-Qdrant backend can be
    substituted without touching callers.
    """

    async def upsert(
        self, id: str, vector: list[float], metadata: dict[str, Any] | None = None
    ) -> None: ...

    async def search(self, query_vector: list[float], top_k: int = 5) -> list[VectorMatch]: ...

    async def delete(self, id: str) -> None: ...


@dataclass(frozen=True)
class GraphNode:
    id: str
    labels: tuple[str, ...] = field(default_factory=tuple)
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    relation: str
    properties: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class KnowledgeGraph(Protocol):
    """Structured relational memory abstraction (GEN-0025 Knowledge Graph Architecture)."""

    async def add_node(
        self, id: str, labels: tuple[str, ...] = (), properties: dict[str, Any] | None = None
    ) -> GraphNode: ...

    async def add_edge(
        self, source: str, target: str, relation: str, properties: dict[str, Any] | None = None
    ) -> GraphEdge: ...

    async def neighbors(self, node_id: str, relation: str | None = None) -> list[GraphNode]: ...
