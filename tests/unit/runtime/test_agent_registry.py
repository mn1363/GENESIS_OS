"""Unit tests for src/runtime/agents/registry.py."""

from __future__ import annotations

import pytest
from src.runtime.agents.registry import (
    AgentAlreadyRegisteredError,
    AgentAvailability,
    AgentNotFoundError,
    AgentRegistry,
)


class _FakeAgent:
    """Minimal `Service` — only `health_check` matters for these tests."""

    def __init__(self, healthy: bool = True) -> None:
        self.healthy = healthy

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def health_check(self) -> bool:
        return self.healthy

    async def on_failure(self, error: BaseException) -> None:
        pass


def _register(
    registry: AgentRegistry,
    agent_id: str = "planner",
    version: str = "1.0.0",
    capabilities: tuple[str, ...] = ("agent.plan@v1",),
    instance: _FakeAgent | None = None,
) -> None:
    registry.register(
        agent_id=agent_id,
        version=version,
        capabilities=capabilities,
        instance=instance or _FakeAgent(),
    )


def test_register_creates_entry_with_active_availability() -> None:
    registry = AgentRegistry()
    _register(registry)

    entry = registry.get("planner")

    assert entry is not None
    assert entry.agent_id == "planner"
    assert entry.version == "1.0.0"
    assert entry.capabilities == ("agent.plan@v1",)
    assert entry.availability is AgentAvailability.ACTIVE
    assert entry.execution_history == []


def test_register_duplicate_agent_id_raises() -> None:
    registry = AgentRegistry()
    _register(registry)

    with pytest.raises(AgentAlreadyRegisteredError):
        _register(registry)


def test_get_unknown_agent_returns_none() -> None:
    assert AgentRegistry().get("missing") is None


def test_all_returns_every_registered_agent() -> None:
    registry = AgentRegistry()
    _register(registry, agent_id="planner")
    _register(registry, agent_id="executor")

    assert {e.agent_id for e in registry.all()} == {"planner", "executor"}


def test_deregister_marks_agent_deregistered_without_removing_it() -> None:
    registry = AgentRegistry()
    _register(registry)

    registry.deregister("planner")

    entry = registry.get("planner")
    assert entry is not None
    assert entry.availability is AgentAvailability.DEREGISTERED


def test_deregister_unknown_agent_raises() -> None:
    with pytest.raises(AgentNotFoundError):
        AgentRegistry().deregister("missing")


def test_find_by_capability_returns_only_matching_active_agents() -> None:
    registry = AgentRegistry()
    _register(registry, agent_id="planner", capabilities=("agent.plan@v1",))
    _register(registry, agent_id="executor", capabilities=("agent.execute@v1",))

    result = registry.find_by_capability("agent.plan@v1")

    assert [e.agent_id for e in result] == ["planner"]


def test_find_by_capability_excludes_deregistered_agents() -> None:
    registry = AgentRegistry()
    _register(registry, agent_id="planner", capabilities=("agent.plan@v1",))
    registry.deregister("planner")

    assert registry.find_by_capability("agent.plan@v1") == []


async def test_refresh_health_marks_unhealthy_agent_unavailable() -> None:
    registry = AgentRegistry()
    agent = _FakeAgent(healthy=False)
    _register(registry, instance=agent)

    healthy = await registry.refresh_health("planner")

    assert healthy is False
    entry = registry.get("planner")
    assert entry is not None
    assert entry.availability is AgentAvailability.UNAVAILABLE
    assert entry.last_health_check is False


async def test_refresh_health_recovers_availability_when_healthy_again() -> None:
    registry = AgentRegistry()
    agent = _FakeAgent(healthy=False)
    _register(registry, instance=agent)
    await registry.refresh_health("planner")

    agent.healthy = True
    healthy = await registry.refresh_health("planner")

    assert healthy is True
    entry = registry.get("planner")
    assert entry is not None
    assert entry.availability is AgentAvailability.ACTIVE


async def test_refresh_health_leaves_deregistered_agents_deregistered() -> None:
    registry = AgentRegistry()
    _register(registry, instance=_FakeAgent(healthy=True))
    registry.deregister("planner")

    await registry.refresh_health("planner")

    entry = registry.get("planner")
    assert entry is not None
    assert entry.availability is AgentAvailability.DEREGISTERED


async def test_refresh_health_unknown_agent_raises() -> None:
    with pytest.raises(AgentNotFoundError):
        await AgentRegistry().refresh_health("missing")


def test_record_execution_appends_to_history() -> None:
    registry = AgentRegistry()
    _register(registry)

    registry.record_execution("planner", success=True, duration_seconds=0.5)
    registry.record_execution("planner", success=False, duration_seconds=1.5)

    entry = registry.get("planner")
    assert entry is not None
    assert len(entry.execution_history) == 2
    assert entry.execution_history[0].success is True
    assert entry.execution_history[1].duration_seconds == 1.5


def test_record_execution_unknown_agent_raises() -> None:
    with pytest.raises(AgentNotFoundError):
        AgentRegistry().record_execution("missing", success=True, duration_seconds=0.1)


def test_failure_rate_is_zero_with_no_history() -> None:
    registry = AgentRegistry()
    _register(registry)

    entry = registry.get("planner")
    assert entry is not None
    assert entry.failure_rate == 0.0


def test_failure_rate_reflects_recorded_failures() -> None:
    registry = AgentRegistry()
    _register(registry)
    registry.record_execution("planner", success=True, duration_seconds=1.0)
    registry.record_execution("planner", success=False, duration_seconds=1.0)
    registry.record_execution("planner", success=False, duration_seconds=1.0)
    registry.record_execution("planner", success=False, duration_seconds=1.0)

    entry = registry.get("planner")
    assert entry is not None
    assert entry.failure_rate == 0.75


def test_average_duration_is_none_with_no_history() -> None:
    registry = AgentRegistry()
    _register(registry)

    entry = registry.get("planner")
    assert entry is not None
    assert entry.average_duration_seconds is None


def test_average_duration_reflects_recorded_durations() -> None:
    registry = AgentRegistry()
    _register(registry)
    registry.record_execution("planner", success=True, duration_seconds=1.0)
    registry.record_execution("planner", success=True, duration_seconds=3.0)

    entry = registry.get("planner")
    assert entry is not None
    assert entry.average_duration_seconds == 2.0
