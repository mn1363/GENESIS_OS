"""Workflow data model (Phase 6 Milestone 4, GEN-0023_Workflow_Runtime.md).

A `Workflow` is a DAG of `WorkflowStep`s (`depends_on` references other
step IDs in the same workflow). Scope note: GEN-0023 also specifies
Checkpoint Recovery and Archival as Workflow Runtime responsibilities —
both are later-phase work layered on the Phase 4 storage layer
(`src/storage/`), not part of this milestone. This module is the "Workflow
Object" GEN-0023 calls for, scoped to what `WorkflowEngine` (`engine.py`)
actually needs to schedule and track execution in one process.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class WorkflowStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    """One node in the workflow DAG.

    `depends_on` holds other steps' `id`s within the same `Workflow` — a
    step only becomes runnable once every dependency has `COMPLETED`
    (GEN-0023's "Execution Coordinator: Manage workflow dependencies").
    """

    id: str
    capability: str
    payload: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING
    task_id: str | None = None
    result: Any = None
    error: str | None = None


@dataclass
class Workflow:
    """A named DAG of steps executed by `WorkflowEngine.run()`."""

    steps: list[WorkflowStep]
    name: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: WorkflowStatus = WorkflowStatus.CREATED

    def step(self, step_id: str) -> WorkflowStep:
        for step in self.steps:
            if step.id == step_id:
                return step
        raise KeyError(f"Unknown step_id: {step_id}")

    def is_complete(self) -> bool:
        terminal = (
            WorkflowStepStatus.COMPLETED,
            WorkflowStepStatus.FAILED,
            WorkflowStepStatus.SKIPPED,
        )
        return all(step.status in terminal for step in self.steps)

    def has_failures(self) -> bool:
        return any(step.status is WorkflowStepStatus.FAILED for step in self.steps)
