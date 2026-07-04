"""Bind the storage layer into the DI Container (Phase 4.2).

Phase 4 scaffold note: the original `wire_storage()` called
`container.register("storage", registry)` — `src.core.di.DIContainer` has
no `register` method (only `register_factory`/`build`), so that call would
raise `AttributeError` against the real container and had never actually
been exercised against it. This fixes that wiring bug in place and extends
it to also register the Phase 4.2 backends (SQL, Redis, Qdrant), all
through `DIContainer.register_factory()` — "wired through dependency
injection only," per `KERNEL_ARCHITECTURE_PROPOSAL.md` §4: components are
constructed by `container.build(name)` in dependency order, never
constructed directly by callers.
"""

from __future__ import annotations

from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis

from src.config.settings import Settings, get_settings
from src.core.di import DIContainer
from src.storage.database import DatabaseSessionManager
from src.storage.event_repository import EventRepository
from src.storage.memory_repository import MemoryRepository
from src.storage.redis_client import RedisRepository, RedisShortTermMemory
from src.storage.repositories import RepositoryRegistry
from src.storage.sql_repository import SQLAlchemyRepository
from src.storage.task_repository import TaskRepository
from src.storage.vector_store import QdrantVectorMemory

DB_SESSION_MANAGER = "db_session_manager"
REDIS_CLIENT = "redis_client"
QDRANT_CLIENT = "qdrant_client"
SQL_TASK_REPOSITORY = "sql_task_repository"
SQL_EVENT_REPOSITORY = "sql_event_repository"
REDIS_CACHE_REPOSITORY = "redis_cache_repository"
SHORT_TERM_MEMORY = "short_term_memory"
VECTOR_MEMORY = "vector_memory"
REPOSITORY_REGISTRY = "repository_registry"


def wire_storage(container: DIContainer, settings: Settings | None = None) -> RepositoryRegistry:
    """Bind storage layer into DI container.

    Registers every storage component as a `DIContainer` factory, then
    builds and returns the `RepositoryRegistry` — the original scaffold's
    three in-memory repositories (`"tasks"`, `"events"`, `"memory"`) are
    kept exactly as they were; the Phase 4.2 durable/production backends
    are added under new names alongside them, so nothing already reading
    from the registry breaks.
    """
    resolved_settings = settings or get_settings()
    _register_factories(container, resolved_settings)
    registry: RepositoryRegistry = container.build(REPOSITORY_REGISTRY)
    return registry


def _register_factories(container: DIContainer, settings: Settings) -> None:
    database_url = settings.database_url
    redis_url = settings.redis_url
    qdrant_host = settings.qdrant_host
    qdrant_port = settings.qdrant_port

    container.register_factory(DB_SESSION_MANAGER, lambda: DatabaseSessionManager(database_url))
    container.register_factory(REDIS_CLIENT, lambda: Redis.from_url(redis_url))
    container.register_factory(
        QDRANT_CLIENT,
        lambda: AsyncQdrantClient(host=qdrant_host, port=qdrant_port, check_compatibility=False),
    )
    container.register_factory(
        SQL_TASK_REPOSITORY,
        lambda db_session_manager: SQLAlchemyRepository(db_session_manager, "tasks"),
        dependencies=[DB_SESSION_MANAGER],
    )
    container.register_factory(
        SQL_EVENT_REPOSITORY,
        lambda db_session_manager: SQLAlchemyRepository(db_session_manager, "events"),
        dependencies=[DB_SESSION_MANAGER],
    )
    container.register_factory(
        REDIS_CACHE_REPOSITORY,
        lambda redis_client: RedisRepository(redis_client, "cache"),
        dependencies=[REDIS_CLIENT],
    )
    container.register_factory(
        SHORT_TERM_MEMORY,
        lambda redis_client: RedisShortTermMemory(redis_client),
        dependencies=[REDIS_CLIENT],
    )
    container.register_factory(
        VECTOR_MEMORY,
        lambda qdrant_client: QdrantVectorMemory(qdrant_client),
        dependencies=[QDRANT_CLIENT],
    )
    container.register_factory(
        REPOSITORY_REGISTRY,
        _build_registry,
        dependencies=[
            SQL_TASK_REPOSITORY,
            SQL_EVENT_REPOSITORY,
            REDIS_CACHE_REPOSITORY,
            SHORT_TERM_MEMORY,
            VECTOR_MEMORY,
        ],
    )


def _build_registry(
    sql_task_repository: SQLAlchemyRepository,
    sql_event_repository: SQLAlchemyRepository,
    redis_cache_repository: RedisRepository,
    short_term_memory: RedisShortTermMemory,
    vector_memory: QdrantVectorMemory,
) -> RepositoryRegistry:
    """Assemble the `RepositoryRegistry`: original in-memory entries plus
    the Phase 4.2 durable/production backends under new names."""
    registry = RepositoryRegistry()
    registry.register("tasks", TaskRepository())
    registry.register("events", EventRepository())
    registry.register("memory", MemoryRepository())
    registry.register("sql_tasks", sql_task_repository)
    registry.register("sql_events", sql_event_repository)
    registry.register("redis_cache", redis_cache_repository)
    registry.register("short_term_memory", short_term_memory)
    registry.register("vector_memory", vector_memory)
    return registry


async def init_storage_schema(container: DIContainer) -> None:
    """Create the SQL storage layer's tables.

    Call once, after `wire_storage()`. Development convenience only — see
    `DatabaseSessionManager.create_all`'s docstring on why this is not a
    migration mechanism.
    """
    session_manager: DatabaseSessionManager = container.build(DB_SESSION_MANAGER)
    await session_manager.create_all()


async def dispose_storage(container: DIContainer) -> None:
    """Dispose of the SQL engine and Redis/Qdrant client connections.

    Call at Kernel shutdown. Safe to call even if some components were
    never built (e.g. only the SQL side was ever used in this process).
    """
    session_manager = container.get_built(DB_SESSION_MANAGER)
    if isinstance(session_manager, DatabaseSessionManager):
        await session_manager.dispose()

    redis_client = container.get_built(REDIS_CLIENT)
    if isinstance(redis_client, Redis):
        await redis_client.aclose()

    qdrant_client = container.get_built(QDRANT_CLIENT)
    if isinstance(qdrant_client, AsyncQdrantClient):
        await qdrant_client.close()
