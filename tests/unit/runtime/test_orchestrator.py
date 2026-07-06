"""Unit tests for src/runtime/agents/orchestrator.py."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from src.core.events import Event, EventBus
from src.core.scheduler import KernelScheduler
from src.core.tasks import TaskStateStore
from src.runtime.agents.communication import AgentCommunicationBus, AgentMessage, AgentMessageType
from src.runtime.agents.orchestrator import (
    AgentOrchestrator,
    NoAgentAvailableError,
    NoCommunicationBusError,
    NoExecutionEngineError,
    Orchestrator,
)
from src.runtime.agents.registry import AgentAvailability, AgentNotFoundError, AgentRegistry
from src.runtime.execution.engine import ExecutionEngine
from src.runtime.execution.models import ExecutionRequest
from src.runtime.execution.providers.local_echo import LocalEchoProvider

pytestmark = pytest.mark.asyncio


class _FakeAgent:
    def __init__(self, healthy: bool = True) -> None:
        self.healthy = healthy
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def health_check(self) -> bool:
        return self.healthy

    async def on_failure(self, error: BaseException) -> None:
        pass


async def _echo_dispatch(capability: str, payload: dict[str, Any]) -> Any:
    return {"capability": capability, "payload": payload}


async def _failing_dispatch(capability: str, payload: dict[str, Any]) -> Any:
    raise RuntimeError("dispatch failed")


def _make_orchestrator(
    dispatch_fn: Any = _echo_dispatch,
    execution_engine: ExecutionEngine | None = None,
    communication_bus: AgentCommunicationBus | None = None,
    health_check_interval_seconds: float = 30.0,
) -> tuple[AgentOrchestrator, AgentRegistry, EventBus, KernelScheduler, TaskStateStore]:
    registry = AgentRegistry()
    event_bus = EventBus()
    task_store = TaskStateStore()
    scheduler = KernelScheduler(task_store=task_store, event_bus=event_bus, dispatch_fn=dispatch_fn)
    orchestrator = AgentOrchestrator(
        registry,
        event_bus,
        scheduler,
        task_store,
        execution_engine=execution_engine,
        communication_bus=communication_bus,
        health_check_interval_seconds=health_check_interval_seconds,
    )
    return orchestrator, registry, event_bus, scheduler, task_store


async def test_agent_orchestrator_satisfies_orchestrator_protocol() -> None:
    orchestrator, *_ = _make_orchestrator()
    assert isinstance(orchestrator, Orchestrator)


# ---- register / start / stop ------------------------------------------------------


async def test_register_agent_records_without_starting() -> None:
    orchestrator, registry, event_bus, _, _ = _make_orchestrator()
    agent = _FakeAgent()
    received: list[dict[str, Any]] = []

    async def _collect(event: Event) -> None:
        received.append(event.payload)

    event_bus.subscribe("agent.registered", _collect)

    entry = await orchestrator.register_agent("planner", "1.0.0", ("agent.plan@v1",), agent)

    assert agent.started is False
    assert entry.agent_id == "planner"
    assert registry.get("planner") is entry
    assert received == [{"agent_id": "planner", "capabilities": ["agent.plan@v1"]}]


async def test_start_agent_requires_prior_registration() -> None:
    orchestrator, *_ = _make_orchestrator()
    with pytest.raises(AgentNotFoundError):
        await orchestrator.start_agent("planner")


async def test_start_agent_starts_and_checks_health() -> None:
    orchestrator, registry, event_bus, _, _ = _make_orchestrator()
    agent = _FakeAgent()
    received: list[dict[str, Any]] = []

    async def _collect(event: Event) -> None:
        received.append(event.payload)

    event_bus.subscribe("agent.started", _collect)
    await orchestrator.register_agent("planner", "1.0.0", ("agent.plan@v1",), agent)

    entry = await orchestrator.start_agent("planner")

    assert agent.started is True
    assert entry.last_health_check is True
    assert received == [{"agent_id": "planner"}]
    assert registry.get("planner") is entry


async def test_stop_agent_stops_and_deregisters() -> None:
    orchestrator, registry, _, _, _ = _make_orchestrator()
    agent = _FakeAgent()
    await orchestrator.register_agent("planner", "1.0.0", ("agent.plan@v1",), agent)
    await orchestrator.start_agent("planner")

    await orchestrator.stop_agent("planner")

    assert agent.stopped is True
    entry = registry.get("planner")
    assert entry is not None
    assert entry.availability is AgentAvailability.DEREGISTERED


async def test_stop_agent_unknown_id_raises() -> None:
    orchestrator, *_ = _make_orchestrator()
    with pytest.raises(AgentNotFoundError):
        await orchestrator.stop_agent("missing")


# ---- discovery --------------------------------------------------------------------


async def test_discover_returns_agents_by_capability() -> None:
    orchestrator, *_ = _make_orchestrator()
    await orchestrator.register_agent("planner", "1.0.0", ("agent.plan@v1",), _FakeAgent())
    await orchestrator.start_agent("planner")

    assert [e.agent_id for e in orchestrator.discover("agent.plan@v1")] == ["planner"]
    assert orchestrator.discover("no.such.capability") == []


# ---- health monitoring: on-demand -----------------------------------------------


async def test_monitor_health_reflects_agent_state() -> None:
    orchestrator, *_ = _make_orchestrator()
    agent = _FakeAgent(healthy=False)
    await orchestrator.register_agent("planner", "1.0.0", ("agent.plan@v1",), agent)
    await orchestrator.start_agent("planner")

    assert await orchestrator.monitor_health("planner") is False


async def test_monitor_health_publishes_changed_event_only_on_transition() -> None:
    orchestrator, _, event_bus, _, _ = _make_orchestrator()
    agent = _FakeAgent(healthy=True)
    changed: list[dict[str, Any]] = []

    async def _collect(event: Event) -> None:
        changed.append(event.payload)

    event_bus.subscribe("agent.health.changed", _collect)
    await orchestrator.register_agent("planner", "1.0.0", ("agent.plan@v1",), agent)
    await orchestrator.start_agent("planner")  # ACTIVE -> ACTIVE via refresh_health: no event yet

    assert changed == []

    agent.healthy = False
    await orchestrator.monitor_health("planner")

    assert len(changed) == 1
    assert changed[0]["agent_id"] == "planner"
    assert changed[0]["availability"] == "unavailable"


async def test_monitor_all_checks_every_active_agent_and_skips_deregistered() -> None:
    orchestrator, *_ = _make_orchestrator()
    await orchestrator.register_agent("planner", "1.0.0", ("agent.plan@v1",), _FakeAgent(True))
    await orchestrator.start_agent("planner")
    await orchestrator.register_agent("executor", "1.0.0", ("agent.execute@v1",), _FakeAgent(False))
    await orchestrator.start_agent("executor")
    await orchestrator.stop_agent("executor")

    assert await orchestrator.monitor_all() == {"planner": True}


# ---- health monitoring: background loop ------------------------------------------


async def test_health_monitoring_loop_runs_periodically() -> None:
    orchestrator, registry, _, _, _ = _make_orchestrator(health_check_interval_seconds=0.01)
    agent = _FakeAgent(healthy=True)
    await orchestrator.register_agent("planner", "1.0.0", ("agent.plan@v1",), agent)
    await orchestrator.start_agent("planner")

    await orchestrator.start_health_monitoring()
    try:
        agent.healthy = False
        for _ in range(50):
            entry = registry.get("planner")
            if entry is not None and entry.availability is AgentAvailability.UNAVAILABLE:
                break
            await asyncio.sleep(0.01)
    finally:
        await orchestrator.stop_health_monitoring()

    entry = registry.get("planner")
    assert entry is not None
    assert entry.availability is AgentAvailability.UNAVAILABLE


async def test_start_health_monitoring_is_idempotent() -> None:
    orchestrator, *_ = _make_orchestrator(health_check_interval_seconds=10.0)
    await orchestrator.start_health_monitoring()
    task_first = orchestrator._monitor_task  # noqa: SLF001
    await orchestrator.start_health_monitoring()
    task_second = orchestrator._monitor_task  # noqa: SLF001

    assert task_first is task_second
    await orchestrator.stop_health_monitoring()


async def test_stop_health_monitoring_without_starting_is_a_no_op() -> None:
    orchestrator, *_ = _make_orchestrator()
    await orchestrator.stop_health_monitoring()  # must not raise


# ---- task dispatch (Scheduler) -----------------------------------------------------


async def test_dispatch_task_raises_when_no_agent_registered() -> None:
    orchestrator, *_ = _make_orchestrator()
    with pytest.raises(NoAgentAvailableError):
        await orchestrator.dispatch_task("agent.execute@v1", {})


async def test_dispatch_task_submits_through_scheduler() -> None:
    orchestrator, _, _, _, task_store = _make_orchestrator()
    await orchestrator.register_agent("executor", "1.0.0", ("agent.execute@v1",), _FakeAgent())
    await orchestrator.start_agent("executor")

    task = await orchestrator.dispatch_task("agent.execute@v1", {"x": 1}, priority=5)

    assert task_store.get(task.id) is not None
    assert task.capability == "agent.execute@v1"
    assert task.priority == 5


async def test_dispatch_task_success_records_execution_history() -> None:
    orchestrator, registry, _, scheduler, _ = _make_orchestrator(dispatch_fn=_echo_dispatch)
    await orchestrator.register_agent("executor", "1.0.0", ("agent.execute@v1",), _FakeAgent())
    await orchestrator.start_agent("executor")

    await scheduler.start()
    try:
        await orchestrator.dispatch_task("agent.execute@v1", {"x": 1})
        for _ in range(50):
            entry = registry.get("executor")
            if entry is not None and entry.execution_history:
                break
            await asyncio.sleep(0.02)
    finally:
        await scheduler.stop(grace_period_seconds=1.0)

    entry = registry.get("executor")
    assert entry is not None
    assert len(entry.execution_history) == 1
    assert entry.execution_history[0].success is True


async def test_dispatch_task_failure_records_execution_history() -> None:
    orchestrator, registry, _, scheduler, _ = _make_orchestrator(dispatch_fn=_failing_dispatch)
    await orchestrator.register_agent("executor", "1.0.0", ("agent.execute@v1",), _FakeAgent())
    await orchestrator.start_agent("executor")

    await scheduler.start()
    try:
        await orchestrator.dispatch_task("agent.execute@v1", {"x": 1})
        for _ in range(50):
            entry = registry.get("executor")
            if entry is not None and entry.execution_history:
                break
            await asyncio.sleep(0.02)
    finally:
        await scheduler.stop(grace_period_seconds=1.0)

    entry = registry.get("executor")
    assert entry is not None
    assert entry.execution_history[0].success is False


async def test_orchestrator_ignores_events_for_unknown_or_missing_task_ids() -> None:
    orchestrator, _, event_bus, _, _ = _make_orchestrator()
    await orchestrator.register_agent("executor", "1.0.0", ("agent.execute@v1",), _FakeAgent())
    await orchestrator.start_agent("executor")

    await event_bus.publish("task.completed", {"task_id": "does-not-exist"})
    await event_bus.publish("task.completed", {})
    await event_bus.publish("task.failed", {"error": "x"})
    # must not raise


# ---- direct execution (Execution Engine integration) --------------------------------


async def test_execute_directly_without_engine_raises() -> None:
    orchestrator, *_ = _make_orchestrator()
    await orchestrator.register_agent("executor", "1.0.0", ("agent.execute@v1",), _FakeAgent())
    await orchestrator.start_agent("executor")

    with pytest.raises(NoExecutionEngineError):
        await orchestrator.execute_directly("agent.execute@v1", {"description": "do X"})


async def test_execute_directly_without_registered_agent_raises() -> None:
    engine = ExecutionEngine([LocalEchoProvider()])
    orchestrator, *_ = _make_orchestrator(execution_engine=engine)

    with pytest.raises(NoAgentAvailableError):
        await orchestrator.execute_directly("agent.execute@v1", {"description": "do X"})


async def test_execute_directly_runs_through_execution_engine_and_records_history() -> None:
    engine = ExecutionEngine([LocalEchoProvider()])
    orchestrator, registry, event_bus, _, _ = _make_orchestrator(execution_engine=engine)
    await orchestrator.register_agent("executor", "1.0.0", ("agent.execute@v1",), _FakeAgent())
    await orchestrator.start_agent("executor")
    received: list[dict[str, Any]] = []

    async def _collect(event: Event) -> None:
        received.append(event.payload)

    event_bus.subscribe("agent.execution.direct_completed", _collect)

    response = await orchestrator.execute_directly("agent.execute@v1", {"description": "do X"})

    assert response.output == "executed: do X"
    entry = registry.get("executor")
    assert entry is not None
    assert len(entry.execution_history) == 1
    assert entry.execution_history[0].success is True
    assert received == [{"capability": "agent.execute@v1", "status": "success"}]


async def test_execute_directly_builds_execution_request_with_given_context() -> None:
    captured: list[ExecutionRequest] = []

    class _CapturingProvider:
        provider_id = "capturing"

        async def health_check(self) -> bool:
            return True

        async def run(self, request: ExecutionRequest) -> str:
            captured.append(request)
            return "ok"

    engine = ExecutionEngine([_CapturingProvider()])
    orchestrator, *_ = _make_orchestrator(execution_engine=engine)
    await orchestrator.register_agent("executor", "1.0.0", ("agent.execute@v1",), _FakeAgent())
    await orchestrator.start_agent("executor")

    await orchestrator.execute_directly("agent.execute@v1", {"description": "do X"})

    assert captured[0].capability == "agent.execute@v1"
    assert captured[0].context == {"description": "do X"}


# ---- send_command (Communication Bus integration) --------------------------------


async def test_send_command_without_communication_bus_raises() -> None:
    orchestrator, *_ = _make_orchestrator()
    await orchestrator.register_agent("planner", "1.0.0", ("agent.plan@v1",), _FakeAgent())
    await orchestrator.start_agent("planner")

    with pytest.raises(NoCommunicationBusError):
        await orchestrator.send_command("planner", {"do": "x"})


async def test_send_command_unknown_agent_raises() -> None:
    comm = AgentCommunicationBus(EventBus())
    orchestrator, *_ = _make_orchestrator(communication_bus=comm)

    with pytest.raises(AgentNotFoundError):
        await orchestrator.send_command("missing", {"do": "x"})


async def test_send_command_delivers_via_communication_bus_only() -> None:
    event_bus = EventBus()
    comm = AgentCommunicationBus(event_bus)
    orchestrator, *_ = _make_orchestrator(communication_bus=comm)
    await orchestrator.register_agent("planner", "1.0.0", ("agent.plan@v1",), _FakeAgent())
    await orchestrator.start_agent("planner")

    received: list[AgentMessage] = []

    async def handler(message: AgentMessage) -> None:
        received.append(message)

    comm.subscribe("planner", handler)

    sent = await orchestrator.send_command("planner", {"do": "replan"})

    assert sent.message_type is AgentMessageType.COMMAND
    assert sent.receiver_id == "planner"
    assert sent.sender_id == "orchestrator"
    assert len(received) == 1
    assert received[0].payload == {"do": "replan"}


async def test_send_command_uses_provided_correlation_id() -> None:
    comm = AgentCommunicationBus(EventBus())
    orchestrator, *_ = _make_orchestrator(communication_bus=comm)
    await orchestrator.register_agent("planner", "1.0.0", ("agent.plan@v1",), _FakeAgent())
    await orchestrator.start_agent("planner")

    sent = await orchestrator.send_command("planner", {}, correlation_id="corr-xyz")

    assert sent.correlation_id == "corr-xyz"
    assert [m.id for m in comm.correlated("corr-xyz")] == [sent.id]
