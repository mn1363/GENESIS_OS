"""Agent Orchestrator (Phase 6 Milestone 2, GEN-0080_Agent_Orchestration_Architecture.md).

Coordinates agent lifecycle (register/start/stop), health monitoring, and
task dispatch on top of existing public interfaces only:

- `AgentRegistry` (Phase 6 Milestone 1, GEN-0007) for discovery and
  bookkeeping — the Orchestrator never holds a bare dict of agents itself.
- `EventBus.subscribe()`/`publish()` (`src/core/events.py`) for lifecycle
  announcements, health-change notifications, and observing task
  outcomes — all coordination is event-driven; nothing here calls into
  another agent directly.
- `KernelScheduler.submit()` (`src/core/scheduler.py`) for actual task
  dispatch — the Orchestrator never runs a capability handler itself.
- `ExecutionEngine.execute()` (`src/runtime/execution/engine.py`, Phase 5)
  for direct, ad-hoc execution outside the Scheduler's task lifecycle
  (health probes, synchronous-style calls) — optional, injected.

`src/core/` is not modified and is not imported for anything beyond these
existing public methods/classes. Per GEN-0007's "Agent Communication:
Allowed: Agent -> Kernel -> Agent. Forbidden: Agent -> Agent" — this class
never gives one agent a reference to another; it only ever calls each
agent's own `Service` lifecycle methods and routes work through the
Scheduler/ExecutionEngine.

Constructed entirely via Dependency Injection: every collaborator
(`AgentRegistry`, `EventBus`, `KernelScheduler`, `TaskStateStore`,
optionally `ExecutionEngine`) is a constructor argument. Fully async;
the only sleep is inside the cancellable background health-monitoring
loop, which never blocks a caller.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any, Protocol, runtime_checkable

from src.core.events import Event, EventBus
from src.core.lifecycle import Service
from src.core.logging import get_logger
from src.core.scheduler import KernelScheduler
from src.core.tasks import Task, TaskStateStore
from src.runtime.agents.registry import (
    AgentAvailability,
    AgentEntry,
    AgentNotFoundError,
    AgentRegistry,
)
from src.runtime.execution.engine import ExecutionEngine
from src.runtime.execution.models import ExecutionRequest, ExecutionResponse, ExecutionStatus

logger = get_logger(__name__)

DEFAULT_HEALTH_CHECK_INTERVAL_SECONDS = 30.0


class NoAgentAvailableError(RuntimeError):
    """Raised when no active agent declares the requested capability."""


class NoExecutionEngineError(RuntimeError):
    """Raised by `execute_directly` when no `ExecutionEngine` was injected."""


@runtime_checkable
class Orchestrator(Protocol):
    """The Agent Orchestrator interface — lifecycle, discovery, dispatch,
    and health monitoring.

    Defined separately from `AgentOrchestrator` so an alternative
    implementation can satisfy the same contract, matching the pattern
    already used for `ProviderAdapter` and `Plugin`.
    """

    async def register_agent(
        self, agent_id: str, version: str, capabilities: tuple[str, ...], instance: Service
    ) -> AgentEntry: ...

    async def start_agent(self, agent_id: str) -> AgentEntry: ...

    async def stop_agent(self, agent_id: str) -> None: ...

    def discover(self, capability: str) -> list[AgentEntry]: ...

    async def monitor_health(self, agent_id: str) -> bool: ...

    async def monitor_all(self) -> dict[str, bool]: ...

    async def dispatch_task(
        self, capability: str, payload: dict[str, Any] | None = None, priority: int = 0
    ) -> Task: ...


class AgentOrchestrator:
    """Concrete `Orchestrator`, composed from injected collaborators only."""

    def __init__(
        self,
        registry: AgentRegistry,
        event_bus: EventBus,
        scheduler: KernelScheduler,
        task_store: TaskStateStore,
        execution_engine: ExecutionEngine | None = None,
        health_check_interval_seconds: float = DEFAULT_HEALTH_CHECK_INTERVAL_SECONDS,
    ) -> None:
        self._registry = registry
        self._events = event_bus
        self._scheduler = scheduler
        self._tasks = task_store
        self._execution_engine = execution_engine
        self._health_check_interval_seconds = health_check_interval_seconds
        self._monitor_task: asyncio.Task[None] | None = None

        self._events.subscribe("task.completed", self._on_task_completed)
        self._events.subscribe("task.failed", self._on_task_failed)

    # ---- Lifecycle: register / start / stop -----------------------------------------

    async def register_agent(
        self, agent_id: str, version: str, capabilities: tuple[str, ...], instance: Service
    ) -> AgentEntry:
        """Record the agent's identity/capabilities in the Agent Registry.
        Does not start it — call `start_agent` separately, matching
        GEN-0007's distinct "registered" vs "running" agent states."""
        entry = self._registry.register(agent_id, version, capabilities, instance)
        await self._events.publish(
            "agent.registered", {"agent_id": agent_id, "capabilities": list(capabilities)}
        )
        logger.info("agent_registered", agent_id=agent_id, capabilities=capabilities)
        return entry

    async def start_agent(self, agent_id: str) -> AgentEntry:
        """Start an already-registered agent's `Service` and record its
        initial health. Raises `AgentNotFoundError` if `agent_id` was
        never registered."""
        entry = self._require(agent_id)
        await entry.instance.start()
        await self._registry.refresh_health(agent_id)
        await self._events.publish("agent.started", {"agent_id": agent_id})
        logger.info("agent_started", agent_id=agent_id)
        return entry

    async def stop_agent(self, agent_id: str) -> None:
        """Stop the agent's `Service` and mark it deregistered in the
        Agent Registry. Raises `AgentNotFoundError` for an unknown
        `agent_id`."""
        entry = self._require(agent_id)
        await entry.instance.stop()
        self._registry.deregister(agent_id)
        await self._events.publish("agent.stopped", {"agent_id": agent_id})
        logger.info("agent_stopped", agent_id=agent_id)

    # ---- Discovery --------------------------------------------------------------

    def discover(self, capability: str) -> list[AgentEntry]:
        """Active agents declaring `capability` — delegates entirely to
        `AgentRegistry.find_by_capability`."""
        return self._registry.find_by_capability(capability)

    # ---- Health monitoring: on-demand + background loop -----------------------------

    async def monitor_health(self, agent_id: str) -> bool:
        """Refresh one agent's health, publishing `agent.health.checked`
        always and `agent.health.changed` only when availability actually
        flipped — so subscribers can react to changes without filtering
        every check themselves."""
        entry = self._require(agent_id)
        previous_availability = entry.availability
        healthy = await self._registry.refresh_health(agent_id)
        await self._events.publish(
            "agent.health.checked", {"agent_id": agent_id, "healthy": healthy}
        )
        if entry.availability != previous_availability:
            await self._events.publish(
                "agent.health.changed",
                {
                    "agent_id": agent_id,
                    "healthy": healthy,
                    "previous_availability": previous_availability.value,
                    "availability": entry.availability.value,
                },
            )
        return healthy

    async def monitor_all(self) -> dict[str, bool]:
        """Health-check every non-deregistered agent. Returns `{agent_id:
        healthy}` for the agents actually checked."""
        results: dict[str, bool] = {}
        for entry in self._registry.all():
            if entry.availability is AgentAvailability.DEREGISTERED:
                continue
            results[entry.agent_id] = await self.monitor_health(entry.agent_id)
        return results

    async def start_health_monitoring(self, interval_seconds: float | None = None) -> None:
        """Start the background health-monitoring loop. A no-op if it's
        already running. Non-blocking: schedules an `asyncio.Task` and
        returns immediately."""
        if self._monitor_task is not None:
            return
        interval = (
            interval_seconds
            if interval_seconds is not None
            else (self._health_check_interval_seconds)
        )
        self._monitor_task = asyncio.create_task(self._health_monitor_loop(interval))

    async def stop_health_monitoring(self) -> None:
        """Cancel the background health-monitoring loop, if running."""
        if self._monitor_task is None:
            return
        self._monitor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._monitor_task
        self._monitor_task = None

    async def _health_monitor_loop(self, interval_seconds: float) -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            await self.monitor_all()

    # ---- Task dispatch (via Scheduler) ---------------------------------------------

    async def dispatch_task(
        self, capability: str, payload: dict[str, Any] | None = None, priority: int = 0
    ) -> Task:
        """Dispatch work for `capability` through the Kernel Scheduler's
        own `submit()` — this class never runs a capability handler
        itself. Raises `NoAgentAvailableError` first if the Agent Registry
        has no active agent for `capability`."""
        if not self.discover(capability):
            raise NoAgentAvailableError(f"No active agent declares capability: {capability}")
        task = await self._scheduler.submit(capability, payload, priority=priority)
        logger.info("task_dispatched", capability=capability, task_id=task.id)
        return task

    # ---- Direct execution (via the Execution Engine) --------------------------------

    async def execute_directly(
        self, capability: str, context: dict[str, Any] | None = None
    ) -> ExecutionResponse:
        """Run `capability` immediately through the injected
        `ExecutionEngine`, bypassing the Scheduler's task queue — for
        ad-hoc calls that don't need admission/retry/priority handling of
        their own. Raises `NoExecutionEngineError` if none was injected,
        or `NoAgentAvailableError` if the Agent Registry has no active
        agent for `capability` (mirrors `dispatch_task`'s discovery gate,
        so a caller can't bypass Agent Registry accounting entirely).
        """
        if self._execution_engine is None:
            raise NoExecutionEngineError("AgentOrchestrator has no ExecutionEngine configured")
        if not self.discover(capability):
            raise NoAgentAvailableError(f"No active agent declares capability: {capability}")

        request = ExecutionRequest(capability=capability, context=context or {})
        response = await self._execution_engine.execute(request)

        for entry in self.discover(capability):
            self._registry.record_execution(
                entry.agent_id,
                success=response.status is ExecutionStatus.SUCCESS,
                duration_seconds=response.latency_seconds,
            )
        await self._events.publish(
            "agent.execution.direct_completed",
            {"capability": capability, "status": response.status.value},
        )
        return response

    # ---- Execution history feedback (via EventBus only) ----------------------------

    async def _on_task_completed(self, event: Event) -> None:
        await self._record_outcome(event.payload.get("task_id"), success=True)

    async def _on_task_failed(self, event: Event) -> None:
        await self._record_outcome(event.payload.get("task_id"), success=False)

    async def _record_outcome(self, task_id: Any, success: bool) -> None:
        """Best-effort: look up the task's capability and record one
        execution history entry (Phase 6 Milestone 1's `AgentRegistry`)
        for every active agent declaring it.

        Known limitation: if more than one agent declares the same
        capability, every one of them is credited/charged for this
        outcome — the Scheduler resolves a capability to exactly one
        `CapabilityRegistry` provider at dispatch time, but that
        resolution isn't observable from here without reaching into
        `src/core/` beyond its public interfaces. With today's agents
        (one capability per agent), this is exact.
        """
        if not isinstance(task_id, str):
            return
        task = self._tasks.get(task_id)
        if task is None:
            return
        duration = max(0.0, time.monotonic() - task.created_at)
        for entry in self.discover(task.capability):
            self._registry.record_execution(
                entry.agent_id, success=success, duration_seconds=duration
            )

    def _require(self, agent_id: str) -> AgentEntry:
        entry = self._registry.get(agent_id)
        if entry is None:
            raise AgentNotFoundError(f"Unknown agent_id: {agent_id}")
        return entry
