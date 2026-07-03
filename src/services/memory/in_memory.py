"""In-memory reference implementations of the memory interfaces.

Explicitly **not** production storage — no persistence, no real Qdrant
client, no real graph database. These exist so the interfaces in
interfaces.py are exercisable by MemoryService and by tests. Swapping in a
real backend later means implementing the same Protocol, not changing any
caller.
"""

from __future__ import annotations

import math
from typing import Any

from src.services.memory.interfaces import GraphEdge, GraphNode, VectorMatch


class InMemoryShortTermMemory:
    """Reference ShortTermMemory — a plain dict, process-lifetime only."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    async def get(self, session_id: str, key: str) -> Any | None:
        return self._store.get(session_id, {}).get(key)

    async def set(self, session_id: str, key: str, value: Any) -> None:
        self._store.setdefault(session_id, {})[key] = value

    async def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)


class InMemoryVectorMemory:
    """Reference VectorMemory — brute-force cosine similarity, no ANN index.

    Stands in for a Qdrant-backed implementation of the same
    `VectorMemory` Protocol. Fine for tests and small data; not intended
    to scale — that's exactly what the real Qdrant adapter (later phase)
    is for.
    """

    def __init__(self) -> None:
        self._vectors: dict[str, tuple[list[float], dict[str, Any]]] = {}

    async def upsert(
        self, id: str, vector: list[float], metadata: dict[str, Any] | None = None
    ) -> None:
        self._vectors[id] = (vector, metadata or {})

    async def search(self, query_vector: list[float], top_k: int = 5) -> list[VectorMatch]:
        scored = [
            VectorMatch(id=vid, score=_cosine_similarity(query_vector, vec), metadata=meta)
            for vid, (vec, meta) in self._vectors.items()
        ]
        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:top_k]

    async def delete(self, id: str) -> None:
        self._vectors.pop(id, None)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemoryKnowledgeGraph:
    """Reference KnowledgeGraph — adjacency dict, process-lifetime only."""

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []

    async def add_node(
        self, id: str, labels: tuple[str, ...] = (), properties: dict[str, Any] | None = None
    ) -> GraphNode:
        node = GraphNode(id=id, labels=labels, properties=properties or {})
        self._nodes[id] = node
        return node

    async def add_edge(
        self, source: str, target: str, relation: str, properties: dict[str, Any] | None = None
    ) -> GraphEdge:
        edge = GraphEdge(
            source=source, target=target, relation=relation, properties=properties or {}
        )
        self._edges.append(edge)
        return edge

    async def neighbors(self, node_id: str, relation: str | None = None) -> list[GraphNode]:
        target_ids = [
            e.target
            for e in self._edges
            if e.source == node_id and (relation is None or e.relation == relation)
        ]
        return [self._nodes[t] for t in target_ids if t in self._nodes]
