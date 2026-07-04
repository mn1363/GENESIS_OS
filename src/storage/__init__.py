"""Storage Layer (Phase 4).

    base.py            -- BaseRepository[T] generic contract
    task_repository.py  -- in-memory TaskRepository (Phase 4 baseline)
    event_repository.py -- in-memory EventRepository (Phase 4 baseline)
    memory_repository.py -- in-memory MemoryRepository (Phase 4 baseline)
    repositories.py     -- RepositoryRegistry
    di_wire.py           -- wire_storage(): binds everything into src.core.di.DIContainer

Phase 4.2 additions:
    database.py          -- DatabaseSessionManager (async SQLAlchemy engine/sessions)
    models.py             -- StorageRecord ORM model
    sql_repository.py     -- SQLAlchemyRepository: SQLite/PostgreSQL adapter
    redis_client.py        -- RedisRepository + RedisShortTermMemory
    vector_store.py        -- QdrantVectorMemory
"""
