"""SQLAlchemy ORM models for the storage layer.

`StorageRecord` (Phase 4.2): a single generic, document-style table rather
than one hand-written model per entity — `sql_repository.SQLAlchemyRepository`
operates on plain `dict[str, Any]` items exactly like the Phase 4 in-memory
`TaskRepository`/`EventRepository`/`MemoryRepository`, so one table keyed
by `(collection, id)` serves all of them without coupling this module to
`src.core.tasks.Task` or `src.core.events.Event` — the sealed core stays
fully decoupled from the storage layer.

`GraphNodeRecord`/`GraphEdgeRecord` (Phase 6 Milestone 6, GEN-0025): unlike
`StorageRecord`, the Knowledge Graph gets dedicated tables rather than
reusing the generic document store — `neighbors()` needs to filter edges
by indexed `source_id`/`relation` columns, which a JSON blob can't do
efficiently. See `src/storage/knowledge_graph.py`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model in the storage layer."""


class StorageRecord(Base):
    """One JSON-document row, namespaced by `collection` (e.g. "tasks")."""

    __tablename__ = "storage_records"

    collection: Mapped[str] = mapped_column(String(64), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class GraphNodeRecord(Base):
    """One Knowledge Graph node, keyed by its caller-chosen `id`."""

    __tablename__ = "knowledge_graph_nodes"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    labels: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class GraphEdgeRecord(Base):
    """One directed Knowledge Graph edge. `id` is a surrogate key (a node
    pair may have more than one edge, e.g. the same relation recorded
    twice, or two different relations) — indexed `source_id`/`relation`
    are what `neighbors()` actually filters on."""

    __tablename__ = "knowledge_graph_edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    relation: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
