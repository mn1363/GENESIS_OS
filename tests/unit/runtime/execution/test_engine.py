"""Unit tests for src/runtime/execution/engine.py."""

from __future__ import annotations

import pytest
from src.runtime.execution.engine import ExecutionEngine
from src.runtime.execution.models import ExecutionRequest, ExecutionStatus
from src.runtime.execution.providers.local_echo import LocalEchoProvider


class _FailingProvider:
    provider_id = "always-fails"

    def __init__(self) -> None:
        self.calls = 0

    async def health_check(self) -> bool:
        return False

    async def run(self, request: ExecutionRequest) -> str:
        self.calls += 1
        raise RuntimeError("simulated provider failure")


class _FlakyProvider:
    """Fails on its first call, succeeds on every call after."""

    provider_id = "flaky"

    def __init__(self) -> None:
        self.calls = 0

    async def health_check(self) -> bool:
        return True

    async def run(self, request: ExecutionRequest) -> str:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("first attempt fails")
        return "recovered"


def _request() -> ExecutionRequest:
    return ExecutionRequest(capability="agent.execute@v1", context={"description": "do X"})


async def test_engine_requires_at_least_one_provider() -> None:
    with pytest.raises(ValueError, match="at least one provider"):
        ExecutionEngine([])


async def test_successful_execution_returns_normalized_response() -> None:
    engine = ExecutionEngine([LocalEchoProvider()])

    response = await engine.execute(_request())

    assert response.status is ExecutionStatus.SUCCESS
    assert response.output == "executed: do X"
    assert response.provider_id == "local-echo"
    assert response.retry_count == 0
    assert response.error is None
    assert response.latency_seconds >= 0.0


async def test_retries_same_provider_before_failing_over() -> None:
    flaky = _FlakyProvider()
    engine = ExecutionEngine([flaky], max_retries_per_provider=1)

    response = await engine.execute(_request())

    assert response.status is ExecutionStatus.SUCCESS
    assert response.output == "recovered"
    assert flaky.calls == 2
    assert response.retry_count == 1


async def test_fails_over_to_next_provider_after_exhausting_retries() -> None:
    failing = _FailingProvider()
    echo = LocalEchoProvider()
    engine = ExecutionEngine([failing, echo], max_retries_per_provider=0)

    response = await engine.execute(_request())

    assert response.status is ExecutionStatus.SUCCESS
    assert response.provider_id == "local-echo"
    assert failing.calls == 1
    assert response.retry_count == 1


async def test_returns_failed_response_when_every_provider_exhausted() -> None:
    first = _FailingProvider()
    second = _FailingProvider()
    engine = ExecutionEngine([first, second], max_retries_per_provider=0)

    response = await engine.execute(_request())

    assert response.status is ExecutionStatus.FAILED
    assert response.output is None
    assert response.error == "simulated provider failure"
    assert response.provider_id == "always-fails"
    assert response.retry_count == 2


async def test_response_request_id_matches_request() -> None:
    engine = ExecutionEngine([LocalEchoProvider()])
    request = _request()

    response = await engine.execute(request)

    assert response.request_id == request.id
