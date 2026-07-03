"""Plan / PlanStep — the data PlannerAgent produces and ExecutorAgent consumes.

Deliberately minimal for Phase 3 (foundation, not real AI planning — see
Phase_3_Implementation_Report.md). Real decomposition logic belongs to a
later phase's Planning Engine (GEN-0006/GEN-0032/GEN-0033).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlanStep:
    description: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True)
class Plan:
    goal: str
    steps: tuple[PlanStep, ...]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
