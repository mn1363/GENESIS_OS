"""Unit tests for src/runtime/agents/."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from src.core.events import Event, EventBus
from src.runtime.agents.critic import CriticAgent
from src.runtime.agents.executor import ExecutorAgent
from src.runtime.agents.planner import PlannerAgent
from src.runtime.execution.engine import ExecutionEngine
from src.runtime.execution.models import ExecutionRequest

pytestmark = pytest.mark.asyncio


async def test_executor_publishes_completion_event() -> None:
    bus = EventBus()
    executor = ExecutorAgent(bus)
    received: list[dict[str, Any]] = []

    async def handler(event: Event) -> None:
        received.append(event.payload)

    bus.subscribe("agent.execution.completed", handler)

    result = await executor.execute({"plan_id": "p1", "step_id": "s1", "description": "do X"})
    assert result["status"] == "executed"
    assert received == [result]


async def test_executor_uses_default_local_echo_engine() -> None:
    """No `engine` passed -> ExecutorAgent(event_bus) still works, and its
    output actually comes from a real ExecutionEngine now, not an inline
    f-string stub."""
    executor = ExecutorAgent(EventBus())
    result = await executor.execute({"plan_id": "p1", "step_id": "s1", "description": "do X"})
    assert result["output"] == "executed: do X"


async def test_executor_accepts_injected_execution_engine() -> None:
    class _StaticProvider:
        provider_id = "static"

        async def health_check(self) -> bool:
            return True

        async def run(self, request: ExecutionRequest) -> str:
            return "custom provider output"

    engine = ExecutionEngine([_StaticProvider()])
    executor = ExecutorAgent(EventBus(), engine=engine)

    result = await executor.execute({"plan_id": "p1", "step_id": "s1", "description": "do X"})

    assert result["output"] == "custom provider output"
    assert result["status"] == "executed"


async def test_executor_reports_failed_status_when_engine_fails() -> None:
    class _AlwaysFailsProvider:
        provider_id = "always-fails"

        async def health_check(self) -> bool:
            return False

        async def run(self, request: ExecutionRequest) -> str:
            raise RuntimeError("boom")

    engine = ExecutionEngine([_AlwaysFailsProvider()], max_retries_per_provider=0)
    executor = ExecutorAgent(EventBus(), engine=engine)

    result = await executor.execute({"plan_id": "p1", "step_id": "s1", "description": "do X"})

    assert result["status"] == "failed"
    assert result["output"] is None


async def test_critic_reacts_to_execution_completed_event() -> None:
    bus = EventBus()
    critic = CriticAgent(bus)
    await critic.start()  # subscribes to agent.execution.completed

    verdicts: list[dict[str, Any]] = []

    async def handler(event: Event) -> None:
        verdicts.append(event.payload)

    bus.subscribe("agent.critique.completed", handler)

    await bus.publish(
        "agent.execution.completed",
        {"plan_id": "p1", "step_id": "s1", "output": "some output"},
    )
    assert verdicts == [{"plan_id": "p1", "step_id": "s1", "verdict": "pass"}]


async def test_critic_fails_on_empty_output() -> None:
    critic = CriticAgent(EventBus())
    result = await critic.critique({"output": ""})
    assert result["verdict"] == "fail"


async def test_planner_submits_one_task_per_step_via_scheduler_not_directly() -> None:
    bus = EventBus()
    submitted: list[tuple[str, dict[str, Any], int]] = []

    async def fake_submit_task(capability: str, payload: dict[str, Any], priority: int) -> Any:
        submitted.append((capability, payload, priority))
        return None

    planner = PlannerAgent(fake_submit_task, bus)
    result = await planner.plan({"goal": "ship the feature"})

    assert len(result["steps"]) == 1
    assert len(submitted) == 1
    capability, payload, _priority = submitted[0]
    assert capability == "agent.execute@v1"
    assert payload["plan_id"] == result["plan_id"]


async def test_full_planner_executor_critic_flow_via_kernel_primitives_only() -> None:
    """End-to-end: Planner never references Executor or Critic directly —
    only kernel.submit_task (faked here) and the shared Event Bus connect them.
    """
    bus = EventBus()
    executor = ExecutorAgent(bus)
    critic = CriticAgent(bus)
    await critic.start()

    async def fake_submit_task(capability: str, payload: dict[str, Any], priority: int) -> Any:
        assert capability == "agent.execute@v1"
        return await executor.execute(payload)

    planner = PlannerAgent(fake_submit_task, bus)

    critiques: list[dict[str, Any]] = []

    async def on_critique(event: Event) -> None:
        critiques.append(event.payload)

    bus.subscribe("agent.critique.completed", on_critique)

    await planner.plan({"goal": "integration test"})
    await asyncio.sleep(0)  # let any pending callbacks flush

    assert len(critiques) == 1
    assert critiques[0]["verdict"] == "pass"
