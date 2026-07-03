"""Smoke-test entrypoint for the Phase 2 deliverable: 'Running Runtime Core'.

Boots the Kernel with a minimal example service, dispatches a call through
capability-based routing, submits a task through the Scheduler, then shuts
down cleanly. Run with: python -m scripts.run_kernel
"""

from __future__ import annotations

import asyncio

from src.core.kernel import Kernel
from src.core.lifecycle import Service


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


if __name__ == "__main__":
    asyncio.run(main())
