"""Kernel Scheduler.

Implements KERNEL_ARCHITECTURE_PROPOSAL.md §3b in full: task scheduling,
priority management, queue management, concurrency control, retry policy,
timeout management, pause/resume, and task cancellation.

"The Scheduler decides when and what to execute. The Execution Engine
executes work." — the Scheduler never calls a concrete service; it calls
`dispatch_fn(capability, payload)`, a callable injected by the Kernel that
routes through the Capability Registry (§3a). This keeps "who answers"
entirely out of the Scheduler's responsibility, per §3b's explicit note.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from typing import Any

from src.core.events import EventBus
from src.core.logging import get_logger
from src.core.tasks import Task, TaskState, TaskStateStore, TaskTransitionError

logger = get_logger(__name__)

DispatchFn = Callable[[str, dict[str, Any]], Awaitable[Any]]


class SchedulerNotRunningError(RuntimeError):
    pass


class KernelScheduler:
    """Owns task admission, ordering, concurrency, retries, timeouts, pause/cancel.

    Not a general-purpose task queue library re-implementation — scoped
    exactly to the eight responsibilities listed in
    KERNEL_ARCHITECTURE_PROPOSAL.md §3b.
    """

    def __init__(
        self,
        task_store: TaskStateStore,
        event_bus: EventBus,
        dispatch_fn: DispatchFn,
        *,
        max_concurrent_tasks: int = 10,
        default_timeout_seconds: float = 300.0,
        default_max_retries: int = 3,
        retry_backoff_base_seconds: float = 1.0,
        max_concurrent_per_capability: dict[str, int] | None = None,
    ) -> None:
        self._store = task_store
        self._events = event_bus
        self._dispatch_fn = dispatch_fn
        self._default_timeout = default_timeout_seconds
        self._default_max_retries = default_max_retries
        self._retry_backoff_base = retry_backoff_base_seconds

        self._global_semaphore = asyncio.Semaphore(max_concurrent_tasks)
        per_capability = max_concurrent_per_capability or {}
        self._capability_semaphores: dict[str, asyncio.Semaphore] = {
            cap: asyncio.Semaphore(limit) for cap, limit in per_capability.items()
        }

        self._paused: set[str] = set()
        self._running_handles: dict[str, asyncio.Task[Any]] = {}
        self._admission_task: asyncio.Task[None] | None = None
        self._running = False
        self._wakeup = asyncio.Event()

    # ---- Task scheduling / queue management -----------------------------------

    async def submit(
        self,
        capability: str,
        payload: dict[str, Any] | None = None,
        priority: int = 0,
        timeout_seconds: float | None = None,
        max_attempts: int | None = None,
    ) -> Task:
        """Create a Task and admit it into the QUEUED state.

        Phase 2 scope note: CREATED -> VALIDATED -> PLANNED are auto-advanced
        here because the Planner/Validation subsystems (GEN-0006, GEN-0032/33)
        are Runtime-layer components not yet implemented in Phase 2 (roadmap
        scope: Kernel/Config/Events/Registry/Logging only). When those
        subsystems exist, this auto-advance is replaced by real dispatch
        calls to `planning.validate_task@v1` / `planning.decompose_task@v1`
        — the Scheduler's job stays the same: admit VALIDATED+PLANNED work
        into QUEUED.
        """
        effective_timeout = (
            timeout_seconds if timeout_seconds is not None else self._default_timeout
        )
        effective_max_attempts = (
            max_attempts if max_attempts is not None else self._default_max_retries
        )
        task = Task(
            capability=capability,
            payload=payload or {},
            priority=priority,
            timeout_seconds=effective_timeout,
            max_attempts=effective_max_attempts,
        )
        self._store.add(task)
        self._store.transition(task.id, TaskState.VALIDATED)
        self._store.transition(task.id, TaskState.PLANNED)
        self._store.transition(task.id, TaskState.QUEUED)
        await self._events.publish("task.created", {"task_id": task.id, "capability": capability})
        await self._events.publish("task.queued", {"task_id": task.id})
        self._wakeup.set()
        return task

    def _queued_tasks_by_priority(self) -> list[Task]:
        now = time.monotonic()
        queued = [
            t for t in self._store.list_by_state(TaskState.QUEUED) if t.id not in self._paused
        ]
        return sorted(queued, key=lambda t: t.effective_priority(now), reverse=True)

    # ---- Concurrency control ----------------------------------------------------

    def _capability_semaphore(self, capability: str) -> asyncio.Semaphore | None:
        return self._capability_semaphores.get(capability)

    # ---- Admission loop -----------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._admission_task = asyncio.create_task(self._admission_loop())
        logger.info("scheduler_started")

    async def stop(self, grace_period_seconds: float = 15.0) -> None:
        """Stop admitting new tasks and drain in-flight ones (§7 of the Kernel proposal)."""
        self._running = False
        self._wakeup.set()
        if self._admission_task is not None:
            await asyncio.wait([self._admission_task], timeout=1.0)

        if self._running_handles:
            done, pending = await asyncio.wait(
                list(self._running_handles.values()), timeout=grace_period_seconds
            )
            for handle in pending:
                handle.cancel()
                for task_id, h in list(self._running_handles.items()):
                    if h is handle:
                        try:
                            self._store.transition(task_id, TaskState.FAILED)
                            self._store.transition(task_id, TaskState.TERMINATED)
                        except TaskTransitionError:
                            pass
        logger.info("scheduler_stopped")

    async def _admission_loop(self) -> None:
        while self._running:
            self._wakeup.clear()
            for task in self._queued_tasks_by_priority():
                if self._global_semaphore.locked():
                    break
                cap_sem = self._capability_semaphore(task.capability)
                if cap_sem is not None and cap_sem.locked():
                    continue
                await self._admit(task)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._wakeup.wait(), timeout=0.5)

    async def _admit(self, task: Task) -> None:
        try:
            self._store.transition(task.id, TaskState.EXECUTING)
        except TaskTransitionError:
            return  # already admitted by a concurrent pass
        await self._events.publish("task.executing", {"task_id": task.id})
        handle = asyncio.create_task(self._run(task))
        self._running_handles[task.id] = handle

    # ---- Execution + timeout + retry ------------------------------------------------

    async def _run(self, task: Task) -> None:
        cap_sem = self._capability_semaphore(task.capability)
        async with self._global_semaphore:
            if cap_sem is not None:
                await cap_sem.acquire()
            try:
                task.attempts += 1
                result = await asyncio.wait_for(
                    self._dispatch_fn(task.capability, task.payload), timeout=task.timeout_seconds
                )
                task.result = result
                self._store.transition(task.id, TaskState.POST_PROCESSING)
                self._store.transition(task.id, TaskState.COMPLETED)
                await self._events.publish("task.completed", {"task_id": task.id})
            except TimeoutError:
                task.error = f"timeout after {task.timeout_seconds}s"
                await self._fail(task)
            except asyncio.CancelledError:
                self._store.transition(task.id, TaskState.TERMINATED)
                await self._events.publish("task.cancelled", {"task_id": task.id})
                raise
            except Exception as exc:  # noqa: BLE001 - isolate failures per BUILD_INSTRUCTION.md
                task.error = str(exc)
                await self._fail(task)
            finally:
                self._running_handles.pop(task.id, None)
                if cap_sem is not None:
                    cap_sem.release()
                self._wakeup.set()

    async def _fail(self, task: Task) -> None:
        self._store.transition(task.id, TaskState.FAILED)
        await self._events.publish(
            "task.failed", {"task_id": task.id, "error": task.error, "attempts": task.attempts}
        )
        if task.attempts < task.max_attempts:
            self._store.transition(task.id, TaskState.RECOVERED)
            backoff = self._retry_backoff_base * (2 ** (task.attempts - 1))
            await self._events.publish(
                "task.retry_scheduled", {"task_id": task.id, "backoff_seconds": backoff}
            )
            asyncio.get_event_loop().call_later(backoff, self._requeue, task.id)
        else:
            self._store.transition(task.id, TaskState.TERMINATED)
            await self._events.publish(
                "task.terminated", {"task_id": task.id, "reason": "max_retries"}
            )

    def _requeue(self, task_id: str) -> None:
        try:
            self._store.transition(task_id, TaskState.QUEUED)
        except TaskTransitionError:
            return
        self._wakeup.set()

    # ---- Pause / Resume --------------------------------------------------------------

    def pause(self, task_id: str) -> None:
        """Pause a QUEUED or EXECUTING task (§3b). Does not discard task state."""
        task = self._store.get(task_id)
        if task is None:
            raise KeyError(task_id)
        self._paused.add(task_id)
        if task.state in (TaskState.QUEUED, TaskState.EXECUTING):
            self._store.transition(task_id, TaskState.PAUSED)
        handle = self._running_handles.get(task_id)
        if handle is not None:
            handle.cancel()

    def resume(self, task_id: str) -> None:
        """Resume a paused task from where the state machine left off (§3b)."""
        self._paused.discard(task_id)
        task = self._store.get(task_id)
        if task is not None and task.state is TaskState.PAUSED:
            self._store.transition(task_id, TaskState.QUEUED)
            self._wakeup.set()

    # ---- Cancellation ------------------------------------------------------------------

    def cancel(self, task_id: str) -> None:
        """Cancel a QUEUED or EXECUTING task, aborting an in-flight step if needed (§3b)."""
        task = self._store.get(task_id)
        if task is None:
            raise KeyError(task_id)
        handle = self._running_handles.get(task_id)
        if handle is not None:
            handle.cancel()  # _run()'s CancelledError branch performs the TERMINATED transition
        elif task.state in (TaskState.QUEUED, TaskState.PAUSED):
            self._store.transition(task_id, TaskState.TERMINATED)
