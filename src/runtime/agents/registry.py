"""Agent Registry (Phase 6, GEN-0007_Agent_Architecture.md §"Agent Registry").

GEN-0007: "The Kernel shall maintain: Agent ID, Version, Capabilities,
Health, Availability, Performance Metrics, Failure Rate, Execution
History" and "Agent Communication: Allowed: Agent -> Kernel -> Agent.
Forbidden: Agent -> Agent."

This is a bookkeeping/discovery layer, not a dispatch mechanism: it never
hands one agent a reference to another, and it does not replace or
duplicate `src.core.registry.CapabilityRegistry` (which the sealed Kernel
already uses for actual dispatch routing). `AgentRegistry` tracks
agent-level metadata `CapabilityRegistry` has no field for — version,
health, availability, per-execution history, failure rate — keyed by
agent ID rather than by capability. Nothing here imports or is imported by
`src/core/`.

Builds only on the existing `src.core.lifecycle.Service` Protocol
(`start`/`stop`/`health_check`/`on_failure`) that `AgentServiceBase`
(`src/runtime/agents/base.py`) already implements — no new agent-facing
interface is introduced.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum

from src.core.lifecycle import Service
from src.core.logging import get_logger

logger = get_logger(__name__)


class AgentAvailability(StrEnum):
    """GEN-0007's "Availability" field."""

    ACTIVE = "active"
    UNAVAILABLE = "unavailable"
    DEREGISTERED = "deregistered"


class AgentAlreadyRegisteredError(RuntimeError):
    """Raised when `agent_id` is already registered."""


class AgentNotFoundError(KeyError):
    """Raised when an operation targets an unregistered `agent_id`."""


@dataclass(frozen=True)
class AgentExecutionRecord:
    """One entry in GEN-0007's "Execution History"."""

    success: bool
    duration_seconds: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentEntry:
    """One agent's full registry record: identity, capabilities, health,
    availability, and derived performance/failure metrics."""

    agent_id: str
    version: str
    capabilities: tuple[str, ...]
    instance: Service
    availability: AgentAvailability = AgentAvailability.ACTIVE
    last_health_check: bool | None = None
    execution_history: list[AgentExecutionRecord] = field(default_factory=list)

    @property
    def failure_rate(self) -> float:
        """GEN-0007's "Failure Rate" — fraction of recorded executions that
        failed. `0.0` (not undefined) when there's no history yet, so
        callers can rank/filter agents without a None-check."""
        if not self.execution_history:
            return 0.0
        failures = sum(1 for record in self.execution_history if not record.success)
        return failures / len(self.execution_history)

    @property
    def average_duration_seconds(self) -> float | None:
        """GEN-0007's "Performance Metrics" — mean duration of every
        recorded execution, successful or not. `None` with no history."""
        if not self.execution_history:
            return None
        total = sum(record.duration_seconds for record in self.execution_history)
        return total / len(self.execution_history)


class AgentRegistry:
    """Tracks every registered agent's identity, capabilities, health,
    availability, and execution history — queryable by ID or by
    capability. Registration/health/history updates are explicit calls
    from whatever owns the agent's lifecycle (e.g. a future Milestone 2
    Orchestrator); `AgentRegistry` does not start, stop, or invoke agents
    itself.
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentEntry] = {}

    def register(
        self, agent_id: str, version: str, capabilities: tuple[str, ...], instance: Service
    ) -> AgentEntry:
        if agent_id in self._agents:
            raise AgentAlreadyRegisteredError(f"Agent already registered: {agent_id}")
        entry = AgentEntry(
            agent_id=agent_id, version=version, capabilities=capabilities, instance=instance
        )
        self._agents[agent_id] = entry
        logger.info(
            "agent_registered", agent_id=agent_id, version=version, capabilities=capabilities
        )
        return entry

    def deregister(self, agent_id: str) -> None:
        entry = self._require(agent_id)
        entry.availability = AgentAvailability.DEREGISTERED
        logger.info("agent_deregistered", agent_id=agent_id)

    def get(self, agent_id: str) -> AgentEntry | None:
        return self._agents.get(agent_id)

    def all(self) -> list[AgentEntry]:
        return list(self._agents.values())

    def find_by_capability(self, capability: str) -> list[AgentEntry]:
        """Active agents (not deregistered) declaring `capability` — a
        discovery query, not a dispatch call; the Kernel Scheduler and
        `CapabilityRegistry` remain the only actual dispatch path."""
        return [
            entry
            for entry in self._agents.values()
            if capability in entry.capabilities
            and entry.availability != AgentAvailability.DEREGISTERED
        ]

    async def refresh_health(self, agent_id: str) -> bool:
        """Call the agent's own `health_check()` (GEN-0007's "Health"),
        record the result, and derive `availability` from it: a
        registered-but-unhealthy agent becomes `UNAVAILABLE`, and a
        recovered one becomes `ACTIVE` again — `DEREGISTERED` agents are
        left alone regardless of health.
        """
        entry = self._require(agent_id)
        healthy = await entry.instance.health_check()
        entry.last_health_check = healthy
        if entry.availability != AgentAvailability.DEREGISTERED:
            entry.availability = (
                AgentAvailability.ACTIVE if healthy else AgentAvailability.UNAVAILABLE
            )
        logger.info("agent_health_checked", agent_id=agent_id, healthy=healthy)
        return healthy

    def record_execution(self, agent_id: str, success: bool, duration_seconds: float) -> None:
        """Append one entry to GEN-0007's "Execution History" for
        `agent_id`, from which `failure_rate`/`average_duration_seconds`
        are derived."""
        entry = self._require(agent_id)
        entry.execution_history.append(
            AgentExecutionRecord(success=success, duration_seconds=duration_seconds)
        )

    def _require(self, agent_id: str) -> AgentEntry:
        entry = self._agents.get(agent_id)
        if entry is None:
            raise AgentNotFoundError(f"Unknown agent_id: {agent_id}")
        return entry
