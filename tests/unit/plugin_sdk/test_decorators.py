"""Unit tests for src/plugin_sdk/decorators.py."""

from __future__ import annotations

from src.plugin_sdk.decorators import event_name_of, on_event


async def test_on_event_attaches_event_name_to_function() -> None:
    @on_event("task.completed")
    async def handler() -> None:
        pass

    assert event_name_of(handler) == "task.completed"


def test_event_name_of_returns_none_for_undecorated_callable() -> None:
    def plain() -> None:
        pass

    assert event_name_of(plain) is None


async def test_on_event_preserves_function_identity_and_callability() -> None:
    calls: list[int] = []

    @on_event("x")
    async def handler(value: int) -> None:
        calls.append(value * 2)

    await handler(3)
    assert calls == [6]
