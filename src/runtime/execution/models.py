"""Execution Engine data model (GEN-0008).

`ExecutionRequest`/`ExecutionResponse` trim GEN-0008's "Standard Execution
Request"/"Standard Execution Response" field lists to what this phase's
engine (`engine.py`) actually uses — project ID, cost estimate, and token
usage are listed in the spec but have no producer yet (no real AI provider
is wired in this phase; see `providers/local_echo.py`), so they're left out
rather than added as always-`None` placeholders.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ExecutionMode(StrEnum):
    """GEN-0008 "Execution Modes"."""

    INTERACTIVE = "interactive"
    BATCH = "batch"
    STREAMING = "streaming"
    BACKGROUND = "background"
    OFFLINE = "offline"


class ExecutionStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True)
class ExecutionRequest:
    """GEN-0008 "Standard Execution Request", trimmed to this phase's fields."""

    capability: str
    context: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mode: ExecutionMode = ExecutionMode.BACKGROUND
    priority: int = 0
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class ExecutionResponse:
    """GEN-0008 "Standard Execution Response", trimmed to this phase's fields."""

    request_id: str
    provider_id: str
    status: ExecutionStatus
    output: Any | None = None
    error: str | None = None
    latency_seconds: float = 0.0
    retry_count: int = 0
