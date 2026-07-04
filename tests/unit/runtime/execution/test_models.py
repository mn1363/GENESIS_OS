"""Unit tests for src/runtime/execution/models.py."""

from __future__ import annotations

from src.runtime.execution.models import (
    ExecutionMode,
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatus,
)


def test_execution_request_defaults() -> None:
    request = ExecutionRequest(capability="agent.execute@v1")

    assert request.context == {}
    assert request.mode is ExecutionMode.BACKGROUND
    assert request.priority == 0
    assert request.timeout_seconds == 30.0
    assert request.id


def test_execution_request_ids_are_unique() -> None:
    a = ExecutionRequest(capability="x")
    b = ExecutionRequest(capability="x")
    assert a.id != b.id


def test_execution_response_success_carries_output_and_no_error() -> None:
    response = ExecutionResponse(
        request_id="r1",
        provider_id="local-echo",
        status=ExecutionStatus.SUCCESS,
        output="executed: do X",
        latency_seconds=0.01,
    )

    assert response.status is ExecutionStatus.SUCCESS
    assert response.output == "executed: do X"
    assert response.error is None
    assert response.retry_count == 0


def test_execution_response_failure_carries_error_and_no_output() -> None:
    response = ExecutionResponse(
        request_id="r1",
        provider_id="local-echo",
        status=ExecutionStatus.FAILED,
        error="boom",
        retry_count=2,
    )

    assert response.status is ExecutionStatus.FAILED
    assert response.output is None
    assert response.error == "boom"
    assert response.retry_count == 2
