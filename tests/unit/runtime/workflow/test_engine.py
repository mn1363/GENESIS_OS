"""Unit tests for src/runtime/workflow/engine.py."""

from __future__ import annotations

from typing import Any

import pytest
from src.core.events import EventBus
from src.core.scheduler import KernelScheduler
from src.core.tasks import TaskStateStore
from src.runtime.agents.orchestrator import AgentOrchestrator
from src.runtime.agents.registry import AgentRegistry
from src.runtime.workflow.engine import WorkflowEngine, WorkflowValidationError
from src.runtime.workflow.models import Workflow, WorkflowStatus, WorkflowStep, WorkflowStepStatus

pytestmark = pytest.mark.asyncio


class _FakeAgent:
    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def health_check(self) -> bool:
        return True

    async def on_failure(self, error: BaseException) -> None:
        pass


async def _echo_dispatch(capability: str, payload: dict[str, Any]) -> Any:
    return {"capability": capability, **payload}


async def _failing_dispatch(capability: str, payload: dict[str, Any]) -> Any:
    if payload.get("fail"):
        raise RuntimeError(f"failed: {capability}")
    return {"capability": capability, **payload}


async def _make_engine(
    dispatch_fn: Any = _echo_dispatch,
    capabilities: tuple[str, ...] = ("agent.execute@v1",),
) -> tuple[WorkflowEngine, EventBus, KernelScheduler]:
    registry = AgentRegistry()
    event_bus = EventBus()
    task_store = TaskStateStore()
    scheduler = KernelScheduler(task_store=task_store, event_bus=event_bus, dispatch_fn=dispatch_fn)
    orchestrator = AgentOrchestrator(registry, event_bus, scheduler, task_store)
    await orchestrator.register_agent("executor", "1.0.0", capabilities, _FakeAgent())
    await orchestrator.start_agent("executor")
    await scheduler.start()
    engine = WorkflowEngine(orchestrator, event_bus, task_store)
    return engine, event_bus, scheduler


async def test_run_executes_linear_workflow_in_order() -> None:
    engine, event_bus, scheduler = await _make_engine()
    events: list[str] = []

    async def _collect(event: Any) -> None:
        events.append(event.name)

    for name in ("workflow.started", "workflow.step.completed", "workflow.completed"):
        event_bus.subscribe(name, _collect)

    workflow = Workflow(
        steps=[
            WorkflowStep(id="s1", capability="agent.execute@v1", payload={"n": 1}),
            WorkflowStep(
                id="s2", capability="agent.execute@v1", payload={"n": 2}, depends_on=("s1",)
            ),
        ]
    )

    try:
        result = await engine.run(workflow)
    finally:
        await scheduler.stop(grace_period_seconds=1.0)

    assert result.status is WorkflowStatus.COMPLETED
    assert result.step("s1").status is WorkflowStepStatus.COMPLETED
    assert result.step("s2").status is WorkflowStepStatus.COMPLETED
    assert result.step("s1").result == {"capability": "agent.execute@v1", "n": 1}
    assert events.count("workflow.started") == 1
    assert events.count("workflow.step.completed") == 2
    assert events.count("workflow.completed") == 1


async def test_run_executes_independent_steps_concurrently() -> None:
    engine, event_bus, scheduler = await _make_engine()

    workflow = Workflow(
        steps=[
            WorkflowStep(id="a", capability="agent.execute@v1"),
            WorkflowStep(id="b", capability="agent.execute@v1"),
        ]
    )

    try:
        result = await engine.run(workflow)
    finally:
        await scheduler.stop(grace_period_seconds=1.0)

    assert result.status is WorkflowStatus.COMPLETED
    assert all(s.status is WorkflowStepStatus.COMPLETED for s in result.steps)


async def test_failed_step_skips_its_dependents_and_marks_workflow_failed() -> None:
    engine, event_bus, scheduler = await _make_engine(dispatch_fn=_failing_dispatch)

    workflow = Workflow(
        steps=[
            WorkflowStep(id="s1", capability="agent.execute@v1", payload={"fail": True}),
            WorkflowStep(id="s2", capability="agent.execute@v1", depends_on=("s1",)),
            WorkflowStep(id="s3", capability="agent.execute@v1"),  # independent, should still run
        ]
    )

    try:
        result = await engine.run(workflow)
    finally:
        await scheduler.stop(grace_period_seconds=1.0)

    assert result.status is WorkflowStatus.FAILED
    assert result.step("s1").status is WorkflowStepStatus.FAILED
    assert result.step("s2").status is WorkflowStepStatus.SKIPPED
    assert result.step("s3").status is WorkflowStepStatus.COMPLETED


async def test_cascading_skip_across_multiple_dependency_hops() -> None:
    engine, event_bus, scheduler = await _make_engine(dispatch_fn=_failing_dispatch)

    workflow = Workflow(
        steps=[
            WorkflowStep(id="s1", capability="agent.execute@v1", payload={"fail": True}),
            WorkflowStep(id="s2", capability="agent.execute@v1", depends_on=("s1",)),
            WorkflowStep(id="s3", capability="agent.execute@v1", depends_on=("s2",)),
        ]
    )

    try:
        result = await engine.run(workflow)
    finally:
        await scheduler.stop(grace_period_seconds=1.0)

    assert result.step("s2").status is WorkflowStepStatus.SKIPPED
    assert result.step("s3").status is WorkflowStepStatus.SKIPPED


async def test_run_rejects_duplicate_step_ids() -> None:
    engine, _, scheduler = await _make_engine()
    workflow = Workflow(
        steps=[
            WorkflowStep(id="s1", capability="agent.execute@v1"),
            WorkflowStep(id="s1", capability="agent.execute@v1"),
        ]
    )
    try:
        with pytest.raises(WorkflowValidationError, match="Duplicate"):
            await engine.run(workflow)
    finally:
        await scheduler.stop(grace_period_seconds=1.0)


async def test_run_rejects_unknown_dependency() -> None:
    engine, _, scheduler = await _make_engine()
    workflow = Workflow(
        steps=[WorkflowStep(id="s1", capability="agent.execute@v1", depends_on=("ghost",))]
    )
    try:
        with pytest.raises(WorkflowValidationError, match="unknown"):
            await engine.run(workflow)
    finally:
        await scheduler.stop(grace_period_seconds=1.0)


async def test_run_rejects_cyclic_dependencies() -> None:
    engine, _, scheduler = await _make_engine()
    workflow = Workflow(
        steps=[
            WorkflowStep(id="a", capability="agent.execute@v1", depends_on=("b",)),
            WorkflowStep(id="b", capability="agent.execute@v1", depends_on=("a",)),
        ]
    )
    try:
        with pytest.raises(WorkflowValidationError, match="Cycle"):
            await engine.run(workflow)
    finally:
        await scheduler.stop(grace_period_seconds=1.0)


async def test_run_publishes_workflow_failed_event_when_a_step_fails() -> None:
    engine, event_bus, scheduler = await _make_engine(dispatch_fn=_failing_dispatch)
    events: list[str] = []

    async def _collect(event: Any) -> None:
        events.append(event.name)

    event_bus.subscribe("workflow.failed", _collect)
    event_bus.subscribe("workflow.step.failed", _collect)

    workflow = Workflow(
        steps=[WorkflowStep(id="s1", capability="agent.execute@v1", payload={"fail": True})]
    )

    try:
        await engine.run(workflow)
    finally:
        await scheduler.stop(grace_period_seconds=1.0)

    assert "workflow.failed" in events
    assert "workflow.step.failed" in events


async def test_engine_ignores_task_events_it_did_not_dispatch() -> None:
    engine, event_bus, scheduler = await _make_engine()
    try:
        await event_bus.publish("task.completed", {"task_id": "not-mine"})
        await event_bus.publish("task.completed", {})
        await event_bus.publish("task.failed", {"task_id": "also-not-mine"})
    finally:
        await scheduler.stop(grace_period_seconds=1.0)
    # must not raise
