"""Integration tests: MemoryService + Kernel, all three production
backends (Phase 6 Milestone 9, GEN-0025).

Milestones 7-8 validated (a) that `wire_memory_service()` correctly wires
all three production backends via Dependency Injection, and (b) that
`MemoryService`'s capability handlers work end-to-end when called
directly against production backend classes. Neither validated the piece
`MemoryService.capability_handlers()` exists for: registering with a real
`Kernel` and being driven through `Kernel.dispatch()` — the actual
integration path a caller uses. This module closes that gap.

No `src/` code changes were needed: `MemoryService` already implements
`Service` and already exposes `capability_handlers()`
(`src/services/memory/service.py`); `Kernel.register_service()`/
`dispatch()`/`boot()`/`shutdown()` are all pre-existing public methods
(`src/core/kernel.py`, unmodified, read-only here). This file is pure
validation.

As in Milestones 7-8's own tests: `wire_memory_service()` builds Redis/
Qdrant clients from real network addresses (`Settings.redis_url`/
`qdrant_host`/`qdrant_port`), and no live Redis/Qdrant server is
available in this environment. To validate the *full* Kernel-dispatch
path for all three backends (not just the Knowledge Graph, which works
standalone against SQLite), these tests construct `MemoryService` with
the same production backend classes `wire_memory_service()` uses, backed
by the same safe test substitutes `tests/unit/storage/` already
established (`fakeredis`, Qdrant's local `":memory:"` mode) — not mocks
of `MemoryService`'s own behavior.
"""

from __future__ import annotations

import pytest
from fakeredis.aioredis import FakeRedis
from qdrant_client import AsyncQdrantClient
from src.config.settings import Settings
from src.core.di import DIContainer
from src.core.kernel import Kernel
from src.core.lifecycle import Service, ServiceLifecycleError
from src.services.memory.di_wire import wire_memory_service
from src.services.memory.service import MemoryService
from src.storage.database import DatabaseSessionManager
from src.storage.di_wire import (
    DB_SESSION_MANAGER,
    QDRANT_CLIENT,
    REDIS_CLIENT,
    dispose_storage,
    init_storage_schema,
    wire_storage,
)
from src.storage.knowledge_graph import SQLAlchemyKnowledgeGraph
from src.storage.redis_client import RedisShortTermMemory
from src.storage.vector_store import QdrantVectorMemory


def _in_memory_settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///:memory:")


async def _production_memory_service() -> MemoryService:
    """A MemoryService built from the same production backend classes
    `wire_memory_service()` uses, with test-safe client substitutes for
    the two that need a live network server in production."""
    db = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")
    await db.create_all()
    return MemoryService(
        short_term=RedisShortTermMemory(FakeRedis()),
        vector=QdrantVectorMemory(AsyncQdrantClient(location=":memory:")),
        graph=SQLAlchemyKnowledgeGraph(db),
    )


def test_memory_service_satisfies_the_service_protocol() -> None:
    assert isinstance(MemoryService(), Service)


async def test_memory_service_on_failure_is_a_safe_no_op() -> None:
    """Completes MemoryService's Service Protocol conformance check: every
    lifecycle method, including the failure hook, is callable and safe."""
    await MemoryService().on_failure(RuntimeError("simulated failure"))


async def test_memory_service_registers_and_boots_under_a_real_kernel() -> None:
    kernel = Kernel()
    memory_service = await _production_memory_service()

    kernel.register_service(
        "memory", memory_service, capability_handlers=memory_service.capability_handlers()
    )
    await kernel.boot()
    try:
        assert set(memory_service.capability_handlers()) <= set(
            kernel.capabilities.all_capabilities()
        )
    finally:
        await kernel.shutdown()


async def test_kernel_boot_reports_an_unhealthy_memory_service_as_a_boot_failure() -> None:
    """Phase 6 Milestone 10: MemoryService.health_check() now genuinely
    reflects backend reachability (src/services/memory/service.py) rather
    than the previous unconditional `return True`. This proves the fix
    changes Kernel's real boot() outcome for the first time: no
    previously-registered Service in this codebase had ever returned
    `False` from `health_check()` during `boot()` before, so this path was
    never actually exercised end-to-end until now.

    Discovered finding, not something this milestone can fix (`src/core/`
    is sealed): `Kernel.boot()` (`src/core/kernel.py`) reacts to
    `health_check() -> False` by calling
    `self.services.set_state(name, ServiceState.DEGRADED)` while the
    service is still in `STARTING` — but `src/core/lifecycle.py`'s own
    state machine only allows `STARTING -> HEALTHY | FAILED`; `DEGRADED`
    is reachable only from `HEALTHY`. So `boot()` raises
    `ServiceLifecycleError` here, not the `KernelBootError` its own
    mandatory-service handling further down the same method appears to
    intend. This reproduces that surprising-but-real behavior rather than
    asserting the presumably-intended one, and documents it as a
    pre-existing core defect this validation work surfaced.
    """

    class _BrokenShortTerm:
        async def get(self, session_id: str, key: str) -> None:
            raise ConnectionError("simulated Redis outage")

        async def set(self, session_id: str, key: str, value: object) -> None:
            raise ConnectionError("simulated Redis outage")

        async def clear(self, session_id: str) -> None:
            raise ConnectionError("simulated Redis outage")

    kernel = Kernel()
    memory_service = MemoryService(short_term=_BrokenShortTerm())
    kernel.register_service(
        "memory", memory_service, capability_handlers=memory_service.capability_handlers()
    )

    with pytest.raises(ServiceLifecycleError, match="starting -> degraded"):
        await kernel.boot()


async def test_kernel_dispatch_drives_short_term_memory_through_all_three_backends() -> None:
    kernel = Kernel()
    memory_service = await _production_memory_service()
    kernel.register_service(
        "memory", memory_service, capability_handlers=memory_service.capability_handlers()
    )
    await kernel.boot()

    try:
        await kernel.dispatch(
            "memory.short_term.set@v1",
            {"session_id": "s1", "key": "topic", "value": "genesis os"},
        )
        result = await kernel.dispatch(
            "memory.short_term.get@v1", {"session_id": "s1", "key": "topic"}
        )
        assert result == "genesis os"
    finally:
        await kernel.shutdown()


async def test_kernel_dispatch_drives_vector_memory_through_all_three_backends() -> None:
    kernel = Kernel()
    memory_service = await _production_memory_service()
    kernel.register_service(
        "memory", memory_service, capability_handlers=memory_service.capability_handlers()
    )
    await kernel.boot()

    try:
        await kernel.dispatch(
            "memory.vector.upsert@v1", {"id": "v1", "vector": [1.0, 0.0], "metadata": {"x": 1}}
        )
        results = await kernel.dispatch(
            "memory.vector.search@v1", {"query_vector": [1.0, 0.0], "top_k": 1}
        )
        assert results == [{"id": "v1", "score": 1.0, "metadata": {"x": 1}}]
    finally:
        await kernel.shutdown()


async def test_kernel_dispatch_drives_knowledge_graph_through_all_three_backends() -> None:
    kernel = Kernel()
    memory_service = await _production_memory_service()
    kernel.register_service(
        "memory", memory_service, capability_handlers=memory_service.capability_handlers()
    )
    await kernel.boot()

    try:
        await kernel.dispatch("memory.graph.add_node@v1", {"id": "alice", "labels": ["person"]})
        await kernel.dispatch("memory.graph.add_node@v1", {"id": "bob", "labels": ["person"]})
        await kernel.dispatch(
            "memory.graph.add_edge@v1",
            {"source": "alice", "target": "bob", "relation": "knows"},
        )
        neighbors = await kernel.dispatch("memory.graph.neighbors@v1", {"node_id": "alice"})
        assert neighbors == [{"id": "bob", "labels": ("person",), "properties": {}}]
    finally:
        await kernel.shutdown()


async def test_every_declared_capability_handler_is_dispatchable() -> None:
    """All 7 capabilities MemoryService.capability_handlers() declares
    must be reachable via Kernel.dispatch(), not just the three exercised
    above in detail."""
    kernel = Kernel()
    memory_service = await _production_memory_service()
    kernel.register_service(
        "memory", memory_service, capability_handlers=memory_service.capability_handlers()
    )
    await kernel.boot()

    try:
        for capability in memory_service.capability_handlers():
            assert kernel.capabilities.resolve(capability) == "memory"
    finally:
        await kernel.shutdown()


async def test_wire_memory_service_composes_with_the_kernels_own_di_container() -> None:
    """The full production chain: Kernel -> kernel.di -> wire_memory_service
    -> MemoryService -> register_service -> dispatch, using the Kernel's
    own DIContainer rather than a bare standalone one.

    Uses `Kernel.dispatch()` directly rather than `kernel.boot()`:
    `wire_memory_service()` builds `short_term`/`vector` from real network
    addresses (`Settings.redis_url`/`qdrant_host`/`qdrant_port`), and no
    live Redis/Qdrant server is available in this environment — Milestone
    10's now-genuine `MemoryService.health_check()` would correctly report
    that as unhealthy, which `kernel.boot()` cannot currently handle
    without raising (see `test_kernel_boot_reports_an_unhealthy_memory_
    service_as_a_boot_failure`'s docstring for the pre-existing `src/core/`
    defect this surfaced). `dispatch()` itself has no such gate — it
    doesn't require `boot()` to have run — so it's the right tool to
    validate DI composition here, independent of that unrelated defect.
    """
    kernel = Kernel(settings=_in_memory_settings())
    memory_service = wire_memory_service(kernel.di, settings=_in_memory_settings())
    await init_storage_schema(kernel.di)

    kernel.register_service(
        "memory", memory_service, capability_handlers=memory_service.capability_handlers()
    )

    try:
        await kernel.dispatch("memory.graph.add_node@v1", {"id": "solo"})
        neighbors = await kernel.dispatch("memory.graph.neighbors@v1", {"node_id": "solo"})
        assert neighbors == []
    finally:
        await dispose_storage(kernel.di)


async def test_dispose_storage_cleans_up_after_full_kernel_lifecycle() -> None:
    """Resources built for a Kernel-registered MemoryService via
    wire_memory_service() must dispose cleanly after Kernel shutdown --
    disposing the shared clients wire_storage() built, since MemoryService
    holds no connections of its own.

    Drives the `Service` lifecycle directly (`start()`/`stop()`) rather
    than through `kernel.boot()`/`shutdown()`, for the same unreachable-
    real-network-backend reason as the test above — `boot()`'s health gate
    is orthogonal to what this test validates (storage disposal).
    """
    container = DIContainer()
    settings = _in_memory_settings()
    memory_service = wire_memory_service(container, settings=settings)
    await init_storage_schema(container)

    await memory_service.start()
    await memory_service.stop()
    await dispose_storage(container)  # must not raise

    assert container.get_built(DB_SESSION_MANAGER) is not None
    assert container.get_built(REDIS_CLIENT) is not None
    assert container.get_built(QDRANT_CLIENT) is not None


async def test_dispose_storage_is_idempotent_after_kernel_integration() -> None:
    container = DIContainer()
    wire_memory_service(container, settings=_in_memory_settings())
    await init_storage_schema(container)

    await dispose_storage(container)
    await dispose_storage(container)  # must not raise the second time either


async def test_repeated_wiring_on_the_same_container_does_not_duplicate_resources() -> None:
    """Calling wire_memory_service() twice on the same container (e.g. a
    caller registering more than one Kernel-facing service against shared
    storage) must reuse the same built instances, not construct new ones."""
    container = DIContainer()
    settings = _in_memory_settings()

    first = wire_memory_service(container, settings=settings)
    second = wire_memory_service(container, settings=settings)

    assert first is second
    assert wire_storage(container, settings=settings).get("sql_tasks") is not None
