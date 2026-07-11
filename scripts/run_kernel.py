"""Smoke-test entrypoint for the Phase 2 deliverable: 'Running Runtime Core'.

Boots the Kernel with a minimal example service, dispatches a call through
capability-based routing, submits a task through the Scheduler, then shuts
down cleanly. Separately, wires the Phase 6 Memory subsystem (Knowledge
Graph, Short-Term, Vector) via Dependency Injection and exercises its
capability handlers directly.

The Memory subsystem is deliberately *not* passed through
`kernel.register_service()` + `kernel.boot()` here: `wire_memory_service()`
builds `short_term`/`vector` from real network addresses
(`Settings.redis_url`/`qdrant_host`/`qdrant_port`), no live Redis/Qdrant
server is available in most local/sandboxed environments, and Phase 6
Milestone 10 made `MemoryService.health_check()` genuinely reflect that
unreachability rather than always reporting healthy. `Kernel.boot()`
cannot currently handle a service reporting unhealthy without raising
(`src/core/kernel.py`'s `STARTING -> DEGRADED` transition is illegal per
`src/core/lifecycle.py` — a pre-existing `src/core/` defect Milestone 10
discovered and documented, not something this script works around by
hiding it). `Kernel.dispatch()` has no such gate, so it's used here
instead — this script stays honestly runnable without live infrastructure.
Run with: python -m scripts.run_kernel
"""

from __future__ import annotations

import asyncio

from src.core.kernel import Kernel
from src.core.lifecycle import Service
from src.services.memory.di_wire import wire_memory_service
from src.storage.di_wire import dispose_storage, init_storage_schema


class EchoService(Service):
    """Minimal example service — not part of the sealed architecture, just
    a stand-in for a real Runtime-layer subsystem so the Kernel has
    something to boot, dispatch to, and shut down."""

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def health_check(self) -> bool:
        return True

    async def on_failure(self, error: BaseException) -> None:
        pass

    async def say(self, payload: dict[str, object]) -> dict[str, object]:
        return {"echo": payload.get("text", "")}


async def main() -> None:
    kernel = Kernel()
    echo_service = EchoService()
    kernel.register_service(
        "echo",
        echo_service,
        capability_handlers={"echo.say@v1": echo_service.say},
    )

    await kernel.boot()
    print("Kernel booted. Registered capabilities:", kernel.capabilities.all_capabilities())

    result = await kernel.dispatch("echo.say@v1", {"text": "hello from the runtime core"})
    print("dispatch() result:", result)

    task = await kernel.submit_task("echo.say@v1", {"text": "scheduled hello"}, priority=1)
    print("Submitted task:", task.id, task.state)

    await asyncio.sleep(0.5)  # let the scheduler's admission loop pick it up
    finished = kernel.tasks.get(task.id)
    print("Task state after scheduling:", finished.state if finished else None)

    await kernel.shutdown()
    print("Kernel shut down cleanly.")

    # Phase 6: wire the Memory subsystem via DI and exercise it directly
    # (see module docstring for why this bypasses register_service()/boot()).
    memory_service = wire_memory_service(kernel.di)
    await init_storage_schema(kernel.di)

    await memory_service.graph_add_node({"id": "genesis-os", "labels": ["system"]})
    neighbors = await memory_service.graph_neighbors({"node_id": "genesis-os"})
    print("Memory subsystem graph_neighbors() result:", neighbors)

    await dispose_storage(kernel.di)
    print("Memory subsystem storage disposed cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
