"""Async database session management (Phase 4.2).

Owns the SQLAlchemy async engine and session factory for whichever
database `Settings.database_url` points at — SQLite (`sqlite+aiosqlite`)
for development, PostgreSQL (`postgresql+asyncpg`) for production, per
GEN-0021_Storage_Architecture / GEN-0061_Storage_Architecture. The dialect
is resolved entirely from the URL scheme; `sql_repository.py` needs no
per-dialect code.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from src.core.logging import get_logger
from src.storage.models import Base

logger = get_logger(__name__)


def _engine_kwargs(database_url: str) -> dict[str, Any]:
    """Extra `create_async_engine` kwargs needed for in-memory SQLite.

    An in-memory SQLite database only exists for the lifetime of a single
    connection; without `StaticPool` each checked-out connection would see
    an empty, unrelated database. File-based SQLite and PostgreSQL need no
    such override.
    """
    if "sqlite" in database_url and ":memory:" in database_url:
        return {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    return {}


class DatabaseSessionManager:
    """Builds and owns the async engine + session factory for one database.

    One instance per process, constructed by the DI Container
    (`src/storage/di_wire.py`) from `Settings.database_url` — never
    constructed directly by repositories or callers.
    """

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._engine: AsyncEngine = create_async_engine(
            database_url, **_engine_kwargs(database_url)
        )
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine, expire_on_commit=False
        )

    async def create_all(self) -> None:
        """Create every table declared on `Base.metadata`.

        Development convenience only — production deployments migrate via
        Alembic (already in `requirements.txt`); this is not a migration tool.
        """
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        logger.info("storage_tables_created", database_url=self._safe_url())

    async def dispose(self) -> None:
        """Dispose of the engine's connection pool. Call at Kernel shutdown."""
        await self._engine.dispose()
        logger.info("storage_engine_disposed", database_url=self._safe_url())

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield an `AsyncSession`, committing on success and rolling back on error."""
        async with self._sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def _safe_url(self) -> str:
        """The configured URL with any credentials stripped, for logging."""
        if "@" in self._database_url:
            scheme, _, tail = self._database_url.partition("://")
            _, _, host_part = tail.partition("@")
            return f"{scheme}://***@{host_part}"
        return self._database_url
