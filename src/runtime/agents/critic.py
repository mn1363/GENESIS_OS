"""Critic Agent.

Never calls, and is never called by, ExecutorAgent directly — it
subscribes to `agent.execution.completed` on the Event Bus in `start()`
(its own `Service` lifecycle hook) and publishes `agent.critique.completed`
with a verdict. This is the second half of the "Agents communicate through
the Kernel Scheduler and Event Bus" decision: Planner->Executor goes
through the Scheduler (a task dispatch), Executor->Critic goes through the
Event Bus (a fire-and-forget notification) — deliberately two different
coordination styles for two different needs (admission-controlled work vs.
observation of a completed result).

Phase 3 scope note: the quality check is a stub (non-empty output passes)
— real evaluation logic is later-phase work (GEN-0009 Quality Engine).
Also exposes `agent.critique@v1` as a directly-dispatchable capability for
callers that want a synchronous critique rather than the event-driven path.
"""

from __future__ import annotations

from typing import Any

from src.core.events import Event, EventBus
from src.runtime.agents.base import AgentServiceBase


class CriticAgent(AgentServiceBase):
    def __init__(self, event_bus: EventBus) -> None:
        self._events = event_bus

    async def start(self) -> None:
        self._events.subscribe("agent.execution.completed", self._on_execution_completed)

    async def _on_execution_completed(self, event: Event) -> None:
        verdict = self._evaluate(event.payload)
        await self._events.publish(
            "agent.critique.completed",
            {
                "plan_id": event.payload.get("plan_id"),
                "step_id": event.payload.get("step_id"),
                "verdict": verdict,
            },
        )

    async def critique(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"verdict": self._evaluate(payload)}

    @staticmethod
    def _evaluate(result: dict[str, Any]) -> str:
        # Phase 3 stub — see module docstring.
        output = result.get("output")
        return "pass" if output else "fail"
