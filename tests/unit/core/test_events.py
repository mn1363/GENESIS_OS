"""Unit tests for src/core/events.py."""

from __future__ import annotations

import pytest
from src.core.events import Event, EventBus

pytestmark = pytest.mark.asyncio


async def test_publish_calls_subscriber() -> None:
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe("task.created", handler)
    await bus.publish("task.created", {"task_id": "abc"})

    assert len(received) == 1
    assert received[0].payload == {"task_id": "abc"}


async def test_publish_with_no_subscribers_does_not_raise() -> None:
    bus = EventBus()
    await bus.publish("nobody.listening", {})  # should not raise


async def test_failing_subscriber_does_not_break_others() -> None:
    bus = EventBus()
    calls: list[str] = []

    async def bad_handler(event: Event) -> None:
        raise ValueError("boom")

    async def good_handler(event: Event) -> None:
        calls.append("good")

    bus.subscribe("x", bad_handler)
    bus.subscribe("x", good_handler)
    await bus.publish("x", {})

    assert calls == ["good"]


async def test_wildcard_subscriber_receives_all_events() -> None:
    bus = EventBus()
    seen: list[str] = []

    async def handler(event: Event) -> None:
        seen.append(event.name)

    bus.subscribe("*", handler)
    await bus.publish("a", {})
    await bus.publish("b", {})

    assert seen == ["a", "b"]


async def test_replay_returns_durable_log() -> None:
    bus = EventBus()
    await bus.publish("task.created", {"id": 1})
    await bus.publish("task.completed", {"id": 1})
    assert len(bus.replay()) == 2
    assert len(bus.replay("task.created")) == 1
