"""Event Bus.

Implements the async channel from KERNEL_ARCHITECTURE_PROPOSAL.md §5
("Asynchronous events... Publishers never know who, if anyone, is
subscribed") and GEN-0015_Event_System's Observable/Replayable principles.

Phase 2 scope note: this is an in-process asyncio pub/sub implementation.
The architecture proposal describes Redis as the pub/sub transport and a
durable relational event log for replay — those are infrastructure
integrations belonging to a later phase (Storage/Database, Phase 2 roadmap
scope is Kernel/Config/Events/Registry/Logging only). This module is built
so that a Redis-backed transport can be substituted behind the same
`EventBus` interface without changing callers — see `_dispatch()`.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)

EventHandler = Callable[["Event"], Awaitable[None]]


@dataclass(frozen=True)
class Event:
    """An immutable event record (GEN-0015: events are immutable and archived)."""

    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)


class EventBus:
    """Publish/subscribe dispatch, plus an in-memory durable log for replay."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._log: list[Event] = []

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Register `handler` to be called for every event published as `event_name`.

        Use "*" to subscribe to all events.
        """
        self._subscribers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        handlers = self._subscribers.get(event_name, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, name: str, payload: dict[str, Any] | None = None) -> Event:
        """Publish an event. Fire-and-forget from the publisher's point of view —
        publishers never know who, if anyone, is subscribed (KERNEL_ARCHITECTURE_PROPOSAL.md §5).
        """
        event = Event(name=name, payload=payload or {})
        self._log.append(event)
        await self._dispatch(event)
        return event

    async def _dispatch(self, event: Event) -> None:
        handlers = list(self._subscribers.get(event.name, [])) + list(
            self._subscribers.get("*", [])
        )
        if not handlers:
            return
        results = await asyncio.gather(
            *(self._safe_call(h, event) for h in handlers), return_exceptions=True
        )
        for result in results:
            if isinstance(result, BaseException):
                logger.error(
                    "event_handler_error",
                    event_name=event.name,
                    event_id=event.id,
                    error=str(result),
                )

    @staticmethod
    async def _safe_call(handler: EventHandler, event: Event) -> None:
        # A failing subscriber must never break publishing for other subscribers
        # or for the publisher — isolation matches BUILD_INSTRUCTION.md's
        # "detect failures, isolate failures" rule.
        await handler(event)

    def replay(self, event_name: str | None = None) -> list[Event]:
        """Return the durable (in-memory, Phase 2) event log, optionally filtered by name."""
        if event_name is None:
            return list(self._log)
        return [e for e in self._log if e.name == event_name]
