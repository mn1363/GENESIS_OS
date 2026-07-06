"""Unit tests for src/runtime/workflow/models.py."""

from __future__ import annotations

import pytest
from src.runtime.workflow.models import (
    Workflow,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepStatus,
)


def _step(step_id: str, status: WorkflowStepStatus = WorkflowStepStatus.PENDING) -> WorkflowStep:
    return WorkflowStep(id=step_id, capability="agent.execute@v1", status=status)


def test_workflow_defaults() -> None:
    workflow = Workflow(steps=[_step("s1")])
    assert workflow.status is WorkflowStatus.CREATED
    assert workflow.id


def test_step_returns_matching_step() -> None:
    step_a = _step("a")
    step_b = _step("b")
    workflow = Workflow(steps=[step_a, step_b])

    assert workflow.step("b") is step_b


def test_step_unknown_id_raises_key_error() -> None:
    workflow = Workflow(steps=[_step("a")])
    with pytest.raises(KeyError):
        workflow.step("missing")


def test_is_complete_false_while_any_step_pending_or_running() -> None:
    workflow = Workflow(
        steps=[
            _step("a", status=WorkflowStepStatus.COMPLETED),
            _step("b", status=WorkflowStepStatus.PENDING),
        ]
    )
    assert workflow.is_complete() is False

    workflow.steps[1].status = WorkflowStepStatus.RUNNING
    assert workflow.is_complete() is False


def test_is_complete_true_when_every_step_is_terminal() -> None:
    workflow = Workflow(
        steps=[
            _step("a", status=WorkflowStepStatus.COMPLETED),
            _step("b", status=WorkflowStepStatus.FAILED),
            _step("c", status=WorkflowStepStatus.SKIPPED),
        ]
    )
    assert workflow.is_complete() is True


def test_has_failures_reflects_any_failed_step() -> None:
    workflow = Workflow(
        steps=[
            _step("a", status=WorkflowStepStatus.COMPLETED),
            _step("b", status=WorkflowStepStatus.FAILED),
        ]
    )
    assert workflow.has_failures() is True

    workflow.steps[1].status = WorkflowStepStatus.COMPLETED
    assert workflow.has_failures() is False
