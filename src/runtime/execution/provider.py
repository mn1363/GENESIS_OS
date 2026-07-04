"""Provider Adapter Interface (GEN-0008).

GEN-0008 lists a large adapter surface (provider name/version, supported
models, auth method, rate limits, ...) that has no consumer yet with a
single, local, always-available provider (`providers/local_echo.py`).
Trimmed to the two members `ExecutionEngine` actually calls; the fuller
interface is additive later, once a second real provider needs it.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.runtime.execution.models import ExecutionRequest


@runtime_checkable
class ProviderAdapter(Protocol):
    """A single execution backend GEN-0008 calls a "Provider" — a remote AI
    API, a local model, a rule-based engine, or an external automation
    tool. `ExecutionEngine` treats every provider identically through this
    interface; it never branches on provider type.
    """

    @property
    def provider_id(self) -> str: ...

    async def health_check(self) -> bool:
        """Cheap liveness check `ExecutionEngine` could use for provider
        selection later; not yet consulted (see `engine.py`'s module
        docstring — "Provider Selection" is a later refinement)."""
        ...

    async def run(self, request: ExecutionRequest) -> Any:
        """Execute `request` and return raw output, or raise on failure —
        `ExecutionEngine` owns timing, retry, and response normalization,
        so adapters stay as thin as possible."""
        ...
