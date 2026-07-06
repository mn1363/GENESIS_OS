"""Workflow Engine (Phase 6 Milestone 4, GEN-0023_Workflow_Runtime.md).

Executes a `Workflow`'s DAG of steps in dependency order, on top of
existing public interfaces only:

- `Orchestrator.dispatch_task()` (Phase 6 Milestone 2,
  `src/runtime/agents/orchestrator.py`) to actually run each step's
  capability — this class never runs a capability handler itself, and
  never talks to the `KernelScheduler` or an agent directly.
- `EventBus.subscribe()` (`src/core/events.py`) on the same
  `task.completed`/`task.failed` events the Orchestrator itself listens to,
  to learn when a dispatched step finished — event-driven, not polling.
- `TaskStateStore.get()` (`src/core/tasks.py`) to read back a finished
  task's `result`/`error` once notified.

`src/core/` is not modified. Covers GEN-0023's Workflow Scheduler +
Execution Coordinator + Task Dispatcher + Completion Manager
responsibilities for one process; Checkpoint Manager and the Archival
lifecycle stage are later-phase work on top of the storage layer
(`src/storage/`) and are out of scope here — see `models.py`'s docstring.

Constructed entirely via Dependency Injection: `Orchestrator`, `EventBus`,
and `TaskStateStore` are all constructor arguments.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.core.events import Event, EventBus
from src.core.logging import get_logger
from src.core.tasks import TaskStateStore
from src.runtime.agents.orchestrator import Orchestrator
from src.runtime.workflow.models import Workflow, WorkflowStatus, WorkflowStep, WorkflowStepStatus

logger = get_logger(__name__)


class WorkflowValidationError(RuntimeError):
    """Raised by `run()` for a malformed workflow: duplicate step IDs,
    a `depends_on` referencing an unknown step, or a dependency cycle."""


class WorkflowEngine:
    """Runs one `Workflow` at a time to completion (steps may themselves
    run concurrently within a dependency "wave"). Not reentrant per
    workflow instance — call `run()` once per `Workflow` object.
    """

    def __init__(
        self, orchestrator: Orchestrator, event_bus: EventBus, task_store: TaskStateStore
    ) -> None:
        self._orchestrator = orchestrator
        self._events = event_bus
        self._tasks = task_store
        self._pending: dict[str, asyncio.Future[None]] = {}
        self._pending_steps: dict[str, tuple[Workflow, WorkflowStep]] = {}

        self._events.subscribe("task.completed", self._on_task_completed)
        self._events.subscribe("task.failed", self._on_task_failed)

    async def run(self, workflow: Workflow) -> Workflow:
        """Execute every step of `workflow`, respecting `depends_on`, and
        return it once every step has reached a terminal status."""
        _validate(workflow)
        workflow.status = WorkflowStatus.RUNNING
        await self._events.publish("workflow.started", {"workflow_id": workflow.id})

        succeeded_ids: set[str] = set()
        processed_ids: set[str] = set()

        while not workflow.is_complete():
            _skip_blocked_steps(workflow, succeeded_ids, processed_ids)

            runnable = [
                step
                for step in workflow.steps
                if step.status is WorkflowStepStatus.PENDING
                and step.id not in processed_ids
                and set(step.depends_on) <= succeeded_ids
            ]
            if not runnable:
                break  # nothing left to run; is_complete() ends the loop next check

            futures = await self._dispatch_wave(workflow, runnable)
            await asyncio.gather(*futures.values())

            for step in runnable:
                processed_ids.add(step.id)
                if step.status is WorkflowStepStatus.COMPLETED:
                    succeeded_ids.add(step.id)

        workflow.status = (
            WorkflowStatus.FAILED if workflow.has_failures() else WorkflowStatus.COMPLETED
        )
        await self._events.publish(
            f"workflow.{workflow.status.value}", {"workflow_id": workflow.id}
        )
        return workflow

    async def _dispatch_wave(
        self, workflow: Workflow, runnable: list[WorkflowStep]
    ) -> dict[str, asyncio.Future[None]]:
        loop = asyncio.get_running_loop()
        futures: dict[str, asyncio.Future[None]] = {}
        for step in runnable:
            step.status = WorkflowStepStatus.RUNNING
            task = await self._orchestrator.dispatch_task(step.capability, step.payload)
            step.task_id = task.id
            future: asyncio.Future[None] = loop.create_future()
            self._pending[task.id] = future
            self._pending_steps[task.id] = (workflow, step)
            futures[step.id] = future
            logger.info(
                "workflow_step_dispatched",
                workflow_id=workflow.id,
                step_id=step.id,
                task_id=task.id,
            )
        return futures

    async def _on_task_completed(self, event: Event) -> None:
        await self._resolve(event.payload.get("task_id"), success=True)

    async def _on_task_failed(self, event: Event) -> None:
        await self._resolve(event.payload.get("task_id"), success=False)

    async def _resolve(self, task_id: Any, success: bool) -> None:
        if not isinstance(task_id, str) or task_id not in self._pending_steps:
            return
        workflow, step = self._pending_steps.pop(task_id)
        future = self._pending.pop(task_id, None)
        task = self._tasks.get(task_id)

        if success:
            step.status = WorkflowStepStatus.COMPLETED
            step.result = task.result if task is not None else None
        else:
            step.status = WorkflowStepStatus.FAILED
            step.error = task.error if task is not None else "unknown error"

        await self._events.publish(
            "workflow.step.completed" if success else "workflow.step.failed",
            {"workflow_id": workflow.id, "step_id": step.id, "task_id": task_id},
        )
        if future is not None and not future.done():
            future.set_result(None)


def _skip_blocked_steps(
    workflow: Workflow, succeeded_ids: set[str], processed_ids: set[str]
) -> None:
    """Mark every not-yet-processed step whose dependency failed or was
    itself skipped as `SKIPPED`, cascading until no more change in one
    pass — a step several hops downstream of a failure must be skipped
    too, not left `PENDING` forever."""
    changed = True
    while changed:
        changed = False
        for step in workflow.steps:
            if step.id in processed_ids:
                continue
            blocked = any(
                dep in processed_ids and dep not in succeeded_ids for dep in step.depends_on
            )
            if blocked:
                step.status = WorkflowStepStatus.SKIPPED
                processed_ids.add(step.id)
                changed = True


def _validate(workflow: Workflow) -> None:
    ids = [step.id for step in workflow.steps]
    if len(ids) != len(set(ids)):
        raise WorkflowValidationError(f"Duplicate step IDs in workflow {workflow.id}")

    known = set(ids)
    for step in workflow.steps:
        unknown = set(step.depends_on) - known
        if unknown:
            raise WorkflowValidationError(
                f"Step {step.id} depends on unknown step(s): {sorted(unknown)}"
            )

    _require_acyclic(workflow)


def _require_acyclic(workflow: Workflow) -> None:
    unresolved = {step.id: set(step.depends_on) for step in workflow.steps}
    resolved: set[str] = set()
    while unresolved:
        ready = [step_id for step_id, deps in unresolved.items() if deps <= resolved]
        if not ready:
            raise WorkflowValidationError(
                f"Cycle detected among step(s): {sorted(unresolved.keys())}"
            )
        for step_id in ready:
            resolved.add(step_id)
            del unresolved[step_id]
