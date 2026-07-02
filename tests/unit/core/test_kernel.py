"""Unit tests for src/core/kernel.py."""

from __future__ import annotations

import pytest
from src.config.settings import Settings, get_settings
from src.core.kernel import Kernel, KernelBootError
from src.core.lifecycle import Service, ServiceState
from src.core.registry import CapabilityNotFoundError

pytestmark = pytest.mark.asyncio


class OkService(Service):
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def health_check(self) -> bool:
        return True

    async def on_failure(self, error: BaseException) -> None:
        pass

    async def echo(self, payload: dict) -> dict:
        return {"echo": payload.get("text")}


class BrokenService(Service):
    async def start(self) -> None:
        raise RuntimeError("boot failure")

    async def stop(self) -> None:
        pass

    async def health_check(self) -> bool:
        return False

    async def on_failure(self, error: BaseException) -> None:
        pass


@pytest.fixture(autouse=True)
def _fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_boot_dispatch_shutdown_roundtrip() -> None:
    kernel = Kernel(settings=Settings())
    svc = OkService()
    kernel.register_service("ok", svc, capability_handlers={"ok.echo@v1": svc.echo})

    await kernel.boot()
    assert svc.started
    assert kernel.services.get("ok").state == ServiceState.HEALTHY

    result = await kernel.dispatch("ok.echo@v1", {"text": "hi"})
    assert result == {"echo": "hi"}

    await kernel.shutdown()
    assert svc.stopped


async def test_mandatory_service_boot_failure_raises() -> None:
    kernel = Kernel(settings=Settings())
    kernel.register_service("broken", BrokenService(), mandatory=True)
    with pytest.raises(KernelBootError):
        await kernel.boot()


async def test_optional_service_boot_failure_does_not_abort() -> None:
    kernel = Kernel(settings=Settings())
    kernel.register_service("broken", BrokenService(), mandatory=False)
    await kernel.boot()  # should not raise
    assert kernel.services.get("broken").state == ServiceState.FAILED


async def test_dispatch_unknown_capability_raises() -> None:
    kernel = Kernel(settings=Settings())
    await kernel.boot()
    with pytest.raises(CapabilityNotFoundError):
        await kernel.dispatch("nonexistent@v1", {})


async def test_submit_task_goes_through_scheduler() -> None:
    kernel = Kernel(settings=Settings())
    svc = OkService()
    kernel.register_service("ok", svc, capability_handlers={"ok.echo@v1": svc.echo})
    await kernel.boot()

    task = await kernel.submit_task("ok.echo@v1", {"text": "scheduled"})
    import asyncio

    await asyncio.sleep(0.2)
    finished = kernel.tasks.get(task.id)
    assert finished is not None
    assert finished.state.value == "completed"

    await kernel.shutdown()
