"""Unit tests for src/core/tasks.py."""

from __future__ import annotations

import pytest
from src.core.tasks import Task, TaskState, TaskStateStore, TaskTransitionError


def test_legal_transition_sequence() -> None:
    store = TaskStateStore()
    task = Task(capability="echo.say@v1")
    store.add(task)
    for target in (
        TaskState.VALIDATED,
        TaskState.PLANNED,
        TaskState.QUEUED,
        TaskState.EXECUTING,
        TaskState.POST_PROCESSING,
        TaskState.COMPLETED,
    ):
        store.transition(task.id, target)
    assert store.get(task.id).state == TaskState.COMPLETED


def test_illegal_transition_raises() -> None:
    store = TaskStateStore()
    task = Task(capability="echo.say@v1")
    store.add(task)
    with pytest.raises(TaskTransitionError):
        store.transition(task.id, TaskState.COMPLETED)  # can't skip straight there


def test_failed_to_recovered_to_queued_retry_path() -> None:
    store = TaskStateStore()
    task = Task(capability="echo.say@v1")
    store.add(task)
    for target in (TaskState.VALIDATED, TaskState.PLANNED, TaskState.QUEUED, TaskState.EXECUTING):
        store.transition(task.id, target)
    store.transition(task.id, TaskState.FAILED)
    store.transition(task.id, TaskState.RECOVERED)
    store.transition(task.id, TaskState.QUEUED)
    assert store.get(task.id).state == TaskState.QUEUED


def test_failed_to_terminated_path() -> None:
    store = TaskStateStore()
    task = Task(capability="echo.say@v1")
    store.add(task)
    for target in (TaskState.VALIDATED, TaskState.PLANNED, TaskState.QUEUED, TaskState.EXECUTING):
        store.transition(task.id, target)
    store.transition(task.id, TaskState.FAILED)
    store.transition(task.id, TaskState.TERMINATED)
    assert store.is_terminal(task.id)


def test_effective_priority_increases_with_age() -> None:
    task = Task(capability="x", priority=1, queued_at=0.0)
    assert task.effective_priority(now=0.0) == 1.0
    assert task.effective_priority(now=60.0) == pytest.approx(3.0)
