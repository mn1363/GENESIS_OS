"""Executor Agent.

Exposes `agent.execute@v1`, admitted only via the Kernel Scheduler (never
called directly by PlannerAgent). Publishes `agent.execution.completed`
so CriticAgent — which has no reference to ExecutorAgent — can react via
the Event Bus, per the Phase 3 "Agents communicate through the Kernel
Scheduler and Event Bus" decision.

Phase 3 scope note: "execution" here is a stub that echoes the step
description back as output — there is no real AI Execution Engine yet
(GEN-0008, later phase). This class exists to prove the multi-agent
coordination pattern (Scheduler-mediated dispatch + event-driven
downstream reaction), not to do real work.
"""

from __future__ import annotations

from typing import Any

from src.core.events import EventBus
from src.runtime.agents.base import AgentServiceBase


class ExecutorAgent(AgentServiceBase):
    def __init__(self, event_bus: EventBus) -> None:
        self._events = event_bus

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan_id = payload["plan_id"]
        step_id = payload["step_id"]
        description = payload["description"]

        # Phase 3 stub — see module docstring.
        output = f"stub output for: {description}"
        result = {"plan_id": plan_id, "step_id": step_id, "status": "executed", "output": output}

        await self._events.publish("agent.execution.completed", result)
        return result
