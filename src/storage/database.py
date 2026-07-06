"""Async database session management (Phase 4.2, hardened GEN-0025).

Owns the SQLAlchemy async engine and session factory for whichever
database `Settings.database_url` points at — SQLite (`sqlite+aiosqlite`)
for development, PostgreSQL (`postgresql+asyncpg`) for production, per
GEN-0021_Storage_Architecture / GEN-0061_Storage_Architecture. The dialect
is resolved entirely from the URL scheme; `sql_repository.py` needs no
per-dialect code.

GEN-0025 hardening: engine/session-factory creation is lazy, deferred from
`__init__` to first actual use (`session()`/`create_all()`/`dispose()`).
`create_async_engine()` resolves and imports the URL's DBAPI driver module
immediately when called — constructing a `DatabaseSessionManager` used to
require `aiosqlite` or `asyncpg` to be installed even if no database
operation was ever attempted. Public API and async behavior are otherwise
unchanged: once anything actually touches the database, driver
availability is still required, exactly as before.
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


def _backend_name(database_url: str) -> str:
    """The backend name implied by `database_url` (e.g. `"sqlite"`,
    `"postgresql"`) — the scheme before any `+driver` suffix. Purely for
    logging/diagnostics here; dialect resolution itself is still entirely
    SQLAlchemy's, from the full URL. (Deliberately not shared with
    `Settings.database_backend` — same trivial computation, kept local so
    `src/storage/` never needs to import `src/config/`.)
    """
    scheme = database_url.split("://", 1)[0]
    return scheme.split("+", 1)[0]


class DatabaseSessionManager:
    """Builds and owns the async engine + session factory for one database.

    One instance per process, constructed by the DI Container
    (`src/storage/di_wire.py`) from `Settings.database_url` — never
    constructed directly by repositories or callers.

    The engine and session factory are built lazily, on first call to
    `session()`, `create_all()`, or `dispose()` — constructing this class
    itself never imports or requires the URL's DBAPI driver (`aiosqlite`,
    `asyncpg`, ...) to be installed.
    """

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    def _ensure_engine(self) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
        """Create the engine and session factory on first use, and reuse
        them on every call after. This is the one place the URL's DBAPI
        driver is actually required to be importable."""
        if self._engine is None:
            self._engine = create_async_engine(
                self._database_url, **_engine_kwargs(self._database_url)
            )
            self._sessionmaker = async_sessionmaker(self._engine, expire_on_commit=False)
            logger.info(
                "storage_engine_created",
                database_url=self._safe_url(),
                backend=_backend_name(self._database_url),
            )
        assert self._sessionmaker is not None  # narrows for mypy; set alongside _engine above
        return self._engine, self._sessionmaker

    async def create_all(self) -> None:
        """Create every table declared on `Base.metadata`.

        Development convenience only — production deployments migrate via
        Alembic (already in `requirements.txt`); this is not a migration tool.
        """
        engine, _ = self._ensure_engine()
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        logger.info("storage_tables_created", database_url=self._safe_url())

    async def dispose(self) -> None:
        """Dispose of the engine's connection pool, if one was ever
        created. A no-op if `session()`/`create_all()` was never called —
        there is nothing to dispose, and doing so would needlessly require
        the DBAPI driver just to tear down a connection that never
        existed. Call at Kernel shutdown."""
        if self._engine is None:
            return
        await self._engine.dispose()
        logger.info("storage_engine_disposed", database_url=self._safe_url())

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield an `AsyncSession`, committing on success and rolling back on error."""
        _, sessionmaker = self._ensure_engine()
        async with sessionmaker() as session:
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
