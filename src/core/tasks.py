"""Task state model + Task State Store.

Implements GENESIS_OS_Runtime_Execution_State_Machine_v1.md's task states,
and KERNEL_ARCHITECTURE_PROPOSAL.md §1's "canonical in-memory state (task
registry...)" — the Kernel is the only component that may mutate a Task's
state; everything else reads it or requests a transition through the
Kernel/Scheduler.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskState(StrEnum):
    """GENESIS_OS_Runtime_Execution_State_Machine_v1.md task states."""

    CREATED = "created"
    VALIDATED = "validated"
    PLANNED = "planned"
    QUEUED = "queued"
    EXECUTING = "executing"
    POST_PROCESSING = "post_processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERED = "recovered"
    TERMINATED = "terminated"
    PAUSED = "paused"  # Kernel Scheduler §3b — orthogonal pause, not in the base state machine


_TERMINAL_STATES = frozenset({TaskState.COMPLETED, TaskState.TERMINATED})

# Legal forward transitions, per the Runtime state machine doc plus the
# Scheduler's FAILED -> (RECOVERED | TERMINATED) branch and PAUSED extension.
_LEGAL_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.CREATED: frozenset({TaskState.VALIDATED, TaskState.TERMINATED}),
    TaskState.VALIDATED: frozenset({TaskState.PLANNED, TaskState.TERMINATED}),
    TaskState.PLANNED: frozenset({TaskState.QUEUED, TaskState.TERMINATED}),
    TaskState.QUEUED: frozenset({TaskState.EXECUTING, TaskState.PAUSED, TaskState.TERMINATED}),
    TaskState.EXECUTING: frozenset(
        {TaskState.POST_PROCESSING, TaskState.FAILED, TaskState.PAUSED, TaskState.TERMINATED}
    ),
    TaskState.POST_PROCESSING: frozenset(
        {TaskState.COMPLETED, TaskState.FAILED, TaskState.TERMINATED}
    ),
    TaskState.FAILED: frozenset({TaskState.RECOVERED, TaskState.TERMINATED}),
    TaskState.RECOVERED: frozenset({TaskState.QUEUED}),
    TaskState.PAUSED: frozenset({TaskState.QUEUED, TaskState.EXECUTING, TaskState.TERMINATED}),
    TaskState.COMPLETED: frozenset(),
    TaskState.TERMINATED: frozenset(),
}


class TaskTransitionError(RuntimeError):
    """Raised when an illegal task state transition is attempted."""


@dataclass
class Task:
    """A unit of work tracked by the Kernel Scheduler."""

    capability: str
    payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # higher = more important
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: TaskState = TaskState.CREATED
    created_at: float = field(default_factory=time.monotonic)
    queued_at: float | None = None
    attempts: int = 0
    max_attempts: int = 3
    timeout_seconds: float = 300.0
    result: Any = None
    error: str | None = None

    def effective_priority(self, now: float | None = None) -> float:
        """Priority adjusted by queue age, to prevent starvation (Kernel §3b)."""
        if self.queued_at is None:
            return float(self.priority)
        now = now if now is not None else time.monotonic()
        age = max(0.0, now - self.queued_at)
        # +1 effective priority point per 30s waited, unbounded.
        return float(self.priority) + (age / 30.0)


class TaskStateStore:
    """In-memory Task State Store.

    KERNEL_ARCHITECTURE_PROPOSAL.md §1 assigns the Kernel ownership of
    canonical task state. This implementation is in-memory for Phase 2
    (matching the roadmap's Phase 2 scope of Runtime Kernel/Config/Events/
    Registry/Logging); durable persistence (surviving process restart, as
    described in §3b for the queue) is deferred to the Storage/Database
    integration in a later phase and is called out as a known gap in the
    Phase 2 report rather than silently assumed.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def add(self, task: Task) -> None:
        self._tasks[task.id] = task

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_by_state(self, state: TaskState) -> list[Task]:
        return [t for t in self._tasks.values() if t.state == state]

    def transition(self, task_id: str, target: TaskState) -> Task:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Unknown task_id: {task_id}")
        legal = _LEGAL_TRANSITIONS[task.state]
        if target not in legal:
            raise TaskTransitionError(
                f"Illegal task state transition for {task_id}: {task.state} -> {target}"
            )
        task.state = target
        if target is TaskState.QUEUED and task.queued_at is None:
            task.queued_at = time.monotonic()
        return task

    def is_terminal(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        return task is not None and task.state in _TERMINAL_STATES

    def all_tasks(self) -> list[Task]:
        return list(self._tasks.values())
