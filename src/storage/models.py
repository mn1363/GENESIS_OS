"""SQLAlchemy ORM model for the SQL-backed repository (Phase 4.2).

A single generic, document-style table rather than one hand-written model
per entity: `sql_repository.SQLAlchemyRepository` operates on plain
`dict[str, Any]` items exactly like the Phase 4 in-memory
`TaskRepository`/`EventRepository`/`MemoryRepository`, so one table keyed
by `(collection, id)` serves all of them without coupling this module to
`src.core.tasks.Task` or `src.core.events.Event` — the sealed core stays
fully decoupled from the storage layer.
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
