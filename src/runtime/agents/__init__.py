"""Multi-Agent Foundation — Planner, Executor, Critic, and (Phase 6) the
Agent Registry and Agent Orchestrator.

Phase 3: agents coordinate only through the Kernel Scheduler
(kernel.submit_task) and the Event Bus — never through direct references
to each other. The Kernel remains the only orchestration point.
"""

from src.runtime.agents.critic import CriticAgent
from src.runtime.agents.executor import ExecutorAgent
from src.runtime.agents.models import Plan, PlanStep
from src.runtime.agents.orchestrator import (
    AgentOrchestrator,
    NoAgentAvailableError,
    NoExecutionEngineError,
    Orchestrator,
)
from src.runtime.agents.planner import PlannerAgent
from src.runtime.agents.registry import (
    AgentAlreadyRegisteredError,
    AgentAvailability,
    AgentEntry,
    AgentExecutionRecord,
    AgentNotFoundError,
    AgentRegistry,
)

__all__ = [
    "PlannerAgent",
    "ExecutorAgent",
    "CriticAgent",
    "Plan",
    "PlanStep",
    "AgentRegistry",
    "AgentEntry",
    "AgentExecutionRecord",
    "AgentAvailability",
    "AgentAlreadyRegisteredError",
    "AgentNotFoundError",
    "AgentOrchestrator",
    "Orchestrator",
    "NoAgentAvailableError",
    "NoExecutionEngineError",
]
