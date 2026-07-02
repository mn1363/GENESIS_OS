"""Unit tests for src/core/scheduler.py."""

from __future__ import annotations

import asyncio

import pytest
from src.core.events import EventBus
from src.core.scheduler import KernelScheduler
from src.core.tasks import TaskState, TaskStateStore

pytestmark = pytest.mark.asyncio


async def _make_scheduler(dispatch_fn, **kwargs) -> KernelScheduler:
    store = TaskStateStore()
    bus = EventBus()
    sched = KernelScheduler(task_store=store, event_bus=bus, dispatch_fn=dispatch_fn, **kwargs)
    return sched


async def test_submitted_task_reaches_completed() -> None:
    async def dispatch_fn(capability: str, payload: dict) -> dict:
        return {"ok": True}

    sched = await _make_scheduler(dispatch_fn)
    await sched.start()
    task = await sched.submit("x.do@v1", {})
    await asyncio.sleep(0.2)
    assert sched._store.get(task.id).state == TaskState.COMPLETED
    await sched.stop()


async def test_failing_task_retries_then_terminates() -> None:
    calls = {"n": 0}

    async def dispatch_fn(capability: str, payload: dict) -> dict:
        calls["n"] += 1
        raise ValueError("always fails")

    sched = await _make_scheduler(
        dispatch_fn, default_max_retries=2, retry_backoff_base_seconds=0.05
    )
    await sched.start()
    task = await sched.submit("x.do@v1", {})
    await asyncio.sleep(1.0)
    final = sched._store.get(task.id)
    assert final.state == TaskState.TERMINATED
    assert calls["n"] == 2
    await sched.stop()


async def test_timeout_marks_task_failed_then_retries() -> None:
    async def dispatch_fn(capability: str, payload: dict) -> dict:
        await asyncio.sleep(1.0)
        return {}

    sched = await _make_scheduler(dispatch_fn, default_max_retries=1)
    await sched.start()
    task = await sched.submit("x.do@v1", {}, timeout_seconds=0.05)
    await asyncio.sleep(0.3)
    final = sched._store.get(task.id)
    assert final.state == TaskState.TERMINATED
    assert "timeout" in (final.error or "")
    await sched.stop()


async def test_priority_ordering() -> None:
    order: list[str] = []

    async def dispatch_fn(capability: str, payload: dict) -> dict:
        order.append(payload["name"])
        return {}

    sched = await _make_scheduler(dispatch_fn, max_concurrent_tasks=1)
    await sched.start()
    await sched.submit("x.do@v1", {"name": "low"}, priority=0)
    await sched.submit("x.do@v1", {"name": "high"}, priority=10)
    await asyncio.sleep(0.3)
    await sched.stop()
    assert order[0] == "high"


async def test_cancel_queued_task() -> None:
    async def dispatch_fn(capability: str, payload: dict) -> dict:
        return {}

    sched = await _make_scheduler(dispatch_fn, max_concurrent_tasks=0)
    task = await sched.submit("x.do@v1", {})
    sched.cancel(task.id)
    assert sched._store.get(task.id).state == TaskState.TERMINATED


async def test_pause_resume() -> None:
    async def dispatch_fn(capability: str, payload: dict) -> dict:
        return {"ok": True}

    sched = await _make_scheduler(dispatch_fn)
    task = await sched.submit("x.do@v1", {})
    sched.pause(task.id)
    assert sched._store.get(task.id).state == TaskState.PAUSED
    sched.resume(task.id)
    assert sched._store.get(task.id).state == TaskState.QUEUED
    await sched.start()
    await asyncio.sleep(0.2)
    assert sched._store.get(task.id).state == TaskState.COMPLETED
    await sched.stop()
