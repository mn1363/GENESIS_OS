"""SQLAlchemy-backed Knowledge Graph (Phase 6 Milestone 6,
GEN-0025_Knowledge_Graph_Architecture.md).

Production implementation of `src.services.memory.interfaces.KnowledgeGraph`
— the Protocol Phase 3 defined and explicitly left with only
`InMemoryKnowledgeGraph` (`src/services/memory/in_memory.py`), documented
there as "explicitly not production storage." Works unmodified against
SQLite or PostgreSQL, exactly like `sql_repository.SQLAlchemyRepository`;
the dialect is entirely determined by the `DatabaseSessionManager` it's
given — no per-dialect code here.

Scope note: GEN-0025's full architecture (Knowledge Extractor, Entity
Resolver, Relationship Builder, Query Engine, Context Engine) is a
multi-stage semantic-extraction pipeline sitting in front of a graph
store. This class is that graph store — the "Knowledge Graph" box in
GEN-0025's pipeline diagram, and the only piece with an existing Protocol
and caller expectation (`KnowledgeGraph`) to satisfy today. The
extraction/resolution/query stages upstream of it have no existing
interface yet and are later-phase work, not part of this milestone.

Callers depend on the `KnowledgeGraph` Protocol, never on this class or on
SQLAlchemy directly — `InMemoryKnowledgeGraph` and
`SQLAlchemyKnowledgeGraph` are interchangeable with no caller changes.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from src.services.memory.interfaces import GraphEdge, GraphNode
from src.storage.database import DatabaseSessionManager
from src.storage.models import GraphEdgeRecord, GraphNodeRecord


class SQLAlchemyKnowledgeGraph:
    """Production `KnowledgeGraph` (GEN-0025), backed by SQLite or PostgreSQL.

    `add_node` upserts by `id` (matching the rest of the storage layer's
    upsert-on-create convention — see `SQLAlchemyRepository.create()`);
    `neighbors()` only returns nodes that were themselves added via
    `add_node`, matching `InMemoryKnowledgeGraph`'s exact semantics: an
    edge to an id never explicitly registered as a node does not surface
    as a neighbor.
    """

    def __init__(self, db_session_manager: DatabaseSessionManager) -> None:
        self._sessions = db_session_manager

    async def add_node(
        self, id: str, labels: tuple[str, ...] = (), properties: dict[str, Any] | None = None
    ) -> GraphNode:
        resolved_properties = properties or {}
        async with self._sessions.session() as session:
            record = await session.get(GraphNodeRecord, id)
            if record is None:
                session.add(
                    GraphNodeRecord(id=id, labels=list(labels), properties=resolved_properties)
                )
            else:
                record.labels = list(labels)
                record.properties = resolved_properties
        return GraphNode(id=id, labels=labels, properties=resolved_properties)

    async def add_edge(
        self, source: str, target: str, relation: str, properties: dict[str, Any] | None = None
    ) -> GraphEdge:
        resolved_properties = properties or {}
        async with self._sessions.session() as session:
            session.add(
                GraphEdgeRecord(
                    id=str(uuid.uuid4()),
                    source_id=source,
                    target_id=target,
                    relation=relation,
                    properties=resolved_properties,
                )
            )
        return GraphEdge(
            source=source, target=target, relation=relation, properties=resolved_properties
        )

    async def neighbors(self, node_id: str, relation: str | None = None) -> list[GraphNode]:
        async with self._sessions.session() as session:
            edge_query = select(GraphEdgeRecord).where(GraphEdgeRecord.source_id == node_id)
            if relation is not None:
                edge_query = edge_query.where(GraphEdgeRecord.relation == relation)
            edge_result = await session.execute(edge_query)
            target_ids = [edge.target_id for edge in edge_result.scalars().all()]
            if not target_ids:
                return []

            seen: set[str] = set()
            ordered_unique_ids: list[str] = []
            for target_id in target_ids:
                if target_id not in seen:
                    seen.add(target_id)
                    ordered_unique_ids.append(target_id)

            node_result = await session.execute(
                select(GraphNodeRecord).where(GraphNodeRecord.id.in_(ordered_unique_ids))
            )
            nodes_by_id = {
                node.id: GraphNode(
                    id=node.id, labels=tuple(node.labels), properties=dict(node.properties)
                )
                for node in node_result.scalars().all()
            }
            return [nodes_by_id[t] for t in ordered_unique_ids if t in nodes_by_id]
