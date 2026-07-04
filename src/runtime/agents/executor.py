"""Executor Agent.

Exposes `agent.execute@v1`, admitted only via the Kernel Scheduler (never
called directly by PlannerAgent). Publishes `agent.execution.completed`
so CriticAgent — which has no reference to ExecutorAgent — can react via
the Event Bus, per the Phase 3 "Agents communicate through the Kernel
Scheduler and Event Bus" decision.

Phase 5: dispatches through a real `ExecutionEngine` (GEN-0008,
`src/runtime/execution/`) instead of the Phase 3 stub that echoed the step
description back inline. Defaults to a single `LocalEchoProvider` if no
`engine` is given, so `ExecutorAgent(event_bus)` still works exactly as
before for any existing caller — only the internals changed.
"""

from __future__ import annotations

from typing import Any

from src.core.events import EventBus
from src.runtime.agents.base import AgentServiceBase
from src.runtime.execution.engine import ExecutionEngine
from src.runtime.execution.models import ExecutionRequest, ExecutionStatus
from src.runtime.execution.providers.local_echo import LocalEchoProvider


class ExecutorAgent(AgentServiceBase):
    def __init__(self, event_bus: EventBus, engine: ExecutionEngine | None = None) -> None:
        self._events = event_bus
        self._engine = engine or ExecutionEngine([LocalEchoProvider()])

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan_id = payload["plan_id"]
        step_id = payload["step_id"]
        description = payload["description"]

        request = ExecutionRequest(
            capability="agent.execute@v1", context={"description": description}
        )
        response = await self._engine.execute(request)

        result = {
            "plan_id": plan_id,
            "step_id": step_id,
            "status": "executed" if response.status is ExecutionStatus.SUCCESS else "failed",
            "output": response.output,
        }

        await self._events.publish("agent.execution.completed", result)
        return result
