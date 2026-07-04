"""Execution Engine (GEN-0008).

Consolidates GEN-0008's "Execution Dispatcher" + "Provider Manager" +
"Retry Manager" + "Execution Monitor" + "Response Normalizer" into one
class rather than five, for this phase's scope: one process, providers
tried in registration order, no cross-process queue. Splitting further is
premature abstraction until a second real provider or a distributed
execution queue (GEN-0008's "Future Extensions") actually needs the seam —
consistent with how Phase 3 kept `PlannerAgent`/`ExecutorAgent`/
`CriticAgent` deliberately simple rather than pre-building machinery no
caller exercises yet.

"Provider Selection" (GEN-0008's pipeline step) here means "try each
registered provider in order, first success wins" — no cost/latency/health
-based ranking yet; `ProviderAdapter.health_check()` is defined for that
future refinement but not consulted today.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from src.core.logging import get_logger
from src.runtime.execution.models import ExecutionRequest, ExecutionResponse, ExecutionStatus
from src.runtime.execution.provider import ProviderAdapter

logger = get_logger(__name__)


class ExecutionEngine:
    """Dispatches an `ExecutionRequest` to the first provider that
    succeeds, retrying each provider up to `max_retries_per_provider`
    times before failing over to the next one (GEN-0008's Retry Policy:
    "Retry Same Provider -> ... -> Retry Different Provider ->
    Escalate to Kernel" — "Escalate to Kernel" here is returning a
    `FAILED` response rather than raising, so the caller decides what to
    do next).
    """

    def __init__(
        self, providers: Sequence[ProviderAdapter], max_retries_per_provider: int = 1
    ) -> None:
        if not providers:
            raise ValueError("ExecutionEngine requires at least one provider")
        self._providers = list(providers)
        self._max_retries_per_provider = max_retries_per_provider

    async def execute(self, request: ExecutionRequest) -> ExecutionResponse:
        retries = 0
        last_error: BaseException | None = None

        for provider in self._providers:
            for attempt in range(self._max_retries_per_provider + 1):
                start = time.monotonic()
                try:
                    output = await provider.run(request)
                except Exception as exc:  # noqa: BLE001 - any provider failure triggers retry/failover
                    last_error = exc
                    retries += 1
                    logger.warning(
                        "execution_attempt_failed",
                        execution_id=request.id,
                        provider_id=provider.provider_id,
                        attempt=attempt,
                        error=str(exc),
                    )
                    continue

                latency = time.monotonic() - start
                logger.info(
                    "execution_succeeded",
                    execution_id=request.id,
                    provider_id=provider.provider_id,
                    latency_seconds=latency,
                    retries=retries,
                )
                return ExecutionResponse(
                    request_id=request.id,
                    provider_id=provider.provider_id,
                    status=ExecutionStatus.SUCCESS,
                    output=output,
                    latency_seconds=latency,
                    retry_count=retries,
                )

        logger.error(
            "execution_all_providers_failed",
            execution_id=request.id,
            providers_tried=[p.provider_id for p in self._providers],
            retries=retries,
        )
        return ExecutionResponse(
            request_id=request.id,
            provider_id=self._providers[-1].provider_id,
            status=ExecutionStatus.FAILED,
            output=None,
            error=str(last_error) if last_error is not None else "no providers available",
            latency_seconds=0.0,
            retry_count=retries,
        )
