"""Planner Agent.

Exposes `agent.plan@v1`. Turns a goal into a `Plan`, then hands each step
to the Kernel Scheduler as a separate task for `agent.execute@v1` —
never calls ExecutorAgent directly. This is what "the Kernel remains the
only orchestration point" means concretely: PlannerAgent's only path to
getting a step executed is `submit_task_fn`, injected at construction,
which is `Kernel.submit_task` bound by the caller — the Planner has no
reference to the Kernel object itself, and no reference to ExecutorAgent.

Phase 3 scope note: decomposition here is a trivial, deterministic stub
(one step per goal) — real multi-step decomposition is later-phase work
(GEN-0032 Task Decomposition Engine), out of scope for this foundation.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from src.core.events import EventBus
from src.core.tasks import Task
from src.runtime.agents.base import AgentServiceBase
from src.runtime.agents.models import Plan, PlanStep

SubmitTaskFn = Callable[[str, dict[str, Any], int], Awaitable[Task]]


class PlannerAgent(AgentServiceBase):
    def __init__(self, submit_task_fn: SubmitTaskFn, event_bus: EventBus) -> None:
        self._submit_task = submit_task_fn
        self._events = event_bus

    async def plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        goal = payload["goal"]
        steps = self._decompose(goal)
        plan = Plan(goal=goal, steps=tuple(steps))

        await self._events.publish(
            "agent.plan.created",
            {"plan_id": plan.id, "goal": plan.goal, "step_count": len(plan.steps)},
        )

        for step in plan.steps:
            await self._submit_task(
                "agent.execute@v1",
                {"plan_id": plan.id, "step_id": step.id, "description": step.description},
                0,
            )

        return {
            "plan_id": plan.id,
            "goal": plan.goal,
            "steps": [{"id": s.id, "description": s.description} for s in plan.steps],
        }

    @staticmethod
    def _decompose(goal: str) -> list[PlanStep]:
        # Phase 3 stub: single-step decomposition. See module docstring.
        return [PlanStep(description=f"Execute: {goal}")]
