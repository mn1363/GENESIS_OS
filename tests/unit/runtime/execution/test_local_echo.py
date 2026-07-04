"""Unit tests for src/runtime/execution/providers/local_echo.py."""

from __future__ import annotations

from src.runtime.execution.models import ExecutionRequest
from src.runtime.execution.provider import ProviderAdapter
from src.runtime.execution.providers.local_echo import LocalEchoProvider


async def test_health_check_is_always_true() -> None:
    assert await LocalEchoProvider().health_check() is True


async def test_run_echoes_description_from_context() -> None:
    provider = LocalEchoProvider()
    request = ExecutionRequest(capability="agent.execute@v1", context={"description": "do X"})

    output = await provider.run(request)

    assert output == "executed: do X"


async def test_run_handles_missing_description() -> None:
    provider = LocalEchoProvider()
    request = ExecutionRequest(capability="agent.execute@v1")

    output = await provider.run(request)

    assert output == "executed: "


def test_local_echo_provider_satisfies_provider_adapter_protocol() -> None:
    assert isinstance(LocalEchoProvider(), ProviderAdapter)
