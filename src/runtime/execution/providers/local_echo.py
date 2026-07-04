"""Local Echo Provider (GEN-0008).

The only `ProviderAdapter` this phase ships: deterministic, in-process, no
credentials or network access required. Exists so `ExecutionEngine` and
`ExecutorAgent` have a real, always-available provider to dispatch to —
GEN-0008's "Local Models"/"Offline Engines" provider categories, not a
stub that pretends to call one. A real remote-AI-provider adapter
(GEN-0008's "Cloud Providers") is later-phase work, added the same way:
implement `ProviderAdapter`, hand it to `ExecutionEngine`, no changes to
either.
"""

from __future__ import annotations

from src.runtime.execution.models import ExecutionRequest


class LocalEchoProvider:
    """Echoes the request's `context["description"]` back as output.

    Always healthy, always succeeds — a fixed point for testing
    `ExecutionEngine`'s dispatch/retry/normalization logic without
    depending on any external provider's availability.
    """

    provider_id = "local-echo"

    async def health_check(self) -> bool:
        return True

    async def run(self, request: ExecutionRequest) -> str:
        description = request.context.get("description", "")
        return f"executed: {description}"
