"""Agent Communication Layer (Phase 6 Milestone 3).

`AgentCommunicationBus` is the *only* way agents exchange messages, and
`EventBus` (`src/core/events.py`) is the *only* transport it uses — every
`AgentMessage` (whether targeted at one agent or broadcast to all) is
carried as the payload of a single well-known `EventBus` channel
(`_MESSAGE_CHANNEL`). There is no separate in-memory call table that
delivers a message directly to a handler outside of an `EventBus`
dispatch: `subscribe()` registers one `EventBus` subscriber per agent on
that shared channel, and that subscriber decides whether the incoming
message is addressed to it (`receiver_id == agent_id`) or is a broadcast
(`receiver_id is None`) before invoking the agent's own handler. No agent
ever holds a reference to another agent, and this bus is not a broker
agents call synchronously — every send is `EventBus.publish()`, fire-and-
forget, exactly like GEN-0007/GEN-0080's "Agent -> Kernel -> Agent" rule
for the Orchestrator.

Reliability is layered on top of `EventBus.publish()`/`subscribe()`
without needing anything from `src/core/` beyond those two public
methods: `EventBus._dispatch` already isolates one subscriber's failure
from the others, but it swallows the exception rather than reporting it
back to the publisher — so retry-with-backoff and dead-lettering happen
*inside* the per-agent subscriber this module registers, not by changing
`EventBus` itself.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from src.core.events import Event, EventBus
from src.core.logging import get_logger

logger = get_logger(__name__)

MAX_DELIVERY_ATTEMPTS = 3
_MESSAGE_CHANNEL = "agent.message"

AgentMessageHandler = Callable[["AgentMessage"], Awaitable[None]]


class AgentMessageType(StrEnum):
    """GEN-0080's "Message Types" for inter-agent communication."""

    EVENT = "event"
    COMMAND = "command"
    RESPONSE = "response"


class AgentAlreadySubscribedError(RuntimeError):
    """Raised when `agent_id` already has a registered handler."""


@dataclass(frozen=True)
class AgentMessage:
    """One message on the Agent Communication Layer.

    `receiver_id=None` means broadcast — delivered to every subscribed
    agent, per "receiver_id (optional broadcast support)"."""

    sender_id: str
    message_type: AgentMessageType
    payload: dict[str, Any] = field(default_factory=dict)
    receiver_id: str | None = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    def to_event_payload(self) -> dict[str, Any]:
        """Serialize to the plain `dict[str, Any]` `EventBus.publish()` requires."""
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "message_type": self.message_type.value,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_event_payload(cls, data: dict[str, Any]) -> AgentMessage:
        """The inverse of `to_event_payload` — reconstructs the message a
        subscriber receives from `Event.payload`."""
        return cls(
            id=data["id"],
            sender_id=data["sender_id"],
            receiver_id=data["receiver_id"],
            message_type=AgentMessageType(data["message_type"]),
            payload=data["payload"],
            correlation_id=data["correlation_id"],
            timestamp=data["timestamp"],
        )


@dataclass(frozen=True)
class DeadLetter:
    """One message that exhausted `MAX_DELIVERY_ATTEMPTS` for one agent."""

    message: AgentMessage
    agent_id: str
    error: str
    attempts: int


class AgentCommunicationBus:
    """Routes `AgentMessage`s between agents, exclusively through
    `EventBus`. Constructed via Dependency Injection — the only
    collaborator is the `EventBus` instance it's given.

    Not a broker: it never calls a handler except from inside an
    `EventBus`-dispatched subscriber, and it never gives one agent a
    reference to another's handler.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._events = event_bus
        self._handlers: dict[str, AgentMessageHandler] = {}
        self._event_subscribers: dict[str, Callable[[Event], Awaitable[None]]] = {}
        self._dead_letters: list[DeadLetter] = []
        self._correlations: dict[str, list[AgentMessage]] = {}

    def subscribe(self, agent_id: str, handler: AgentMessageHandler) -> None:
        """Register `handler` as `agent_id`'s message handler.

        Internally, this is exactly one `EventBus.subscribe()` call on the
        shared `_MESSAGE_CHANNEL` — "receive messages via subscription
        only" all the way down to the transport.
        """
        if agent_id in self._handlers:
            raise AgentAlreadySubscribedError(f"Agent already subscribed: {agent_id}")

        self._handlers[agent_id] = handler

        async def _on_event(event: Event) -> None:
            message = AgentMessage.from_event_payload(event.payload)
            if message.receiver_id is not None and message.receiver_id != agent_id:
                return
            if message.sender_id == agent_id:
                return
            await self._deliver(agent_id, handler, message)

        self._event_subscribers[agent_id] = _on_event
        self._events.subscribe(_MESSAGE_CHANNEL, _on_event)
        logger.info("agent_message_subscribed", agent_id=agent_id)

    def unsubscribe(self, agent_id: str) -> None:
        """Remove `agent_id`'s subscription, if any. A no-op for an
        unknown `agent_id` — mirrors `EventBus.unsubscribe`'s own
        tolerance of unknown handlers."""
        subscriber = self._event_subscribers.pop(agent_id, None)
        self._handlers.pop(agent_id, None)
        if subscriber is not None:
            self._events.unsubscribe(_MESSAGE_CHANNEL, subscriber)
            logger.info("agent_message_unsubscribed", agent_id=agent_id)

    async def publish(self, message: AgentMessage) -> None:
        """Send `message` — to one agent (`receiver_id` set) or to every
        subscriber (`receiver_id=None`) — via `EventBus.publish()` only.
        """
        self._correlations.setdefault(message.correlation_id, []).append(message)
        await self._events.publish(_MESSAGE_CHANNEL, message.to_event_payload())

    async def broadcast(
        self,
        sender_id: str,
        message_type: AgentMessageType,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> AgentMessage:
        """Convenience for publishing a `receiver_id=None` broadcast message."""
        message = AgentMessage(
            sender_id=sender_id,
            receiver_id=None,
            message_type=message_type,
            payload=payload or {},
            correlation_id=correlation_id or str(uuid.uuid4()),
        )
        await self.publish(message)
        return message

    def dead_letters(self) -> list[DeadLetter]:
        """Every message that exhausted delivery retries for some agent."""
        return list(self._dead_letters)

    def correlated(self, correlation_id: str) -> list[AgentMessage]:
        """Every message published under `correlation_id`, in publish order."""
        return list(self._correlations.get(correlation_id, []))

    async def _deliver(
        self, agent_id: str, handler: AgentMessageHandler, message: AgentMessage
    ) -> None:
        """Invoke `handler(message)`, retrying up to `MAX_DELIVERY_ATTEMPTS`
        times before recording a `DeadLetter`. Runs entirely inside the
        `EventBus`-dispatched subscriber for `agent_id` — `EventBus`
        itself already isolates this from other agents' subscribers, this
        retry loop only concerns `agent_id`'s own delivery.
        """
        last_error: BaseException | None = None
        for attempt in range(1, MAX_DELIVERY_ATTEMPTS + 1):
            try:
                await handler(message)
                return
            except Exception as exc:  # noqa: BLE001 - any handler failure is retried, then dead-lettered
                last_error = exc
                logger.warning(
                    "agent_message_delivery_failed",
                    agent_id=agent_id,
                    message_id=message.id,
                    attempt=attempt,
                    error=str(exc),
                )

        self._dead_letters.append(
            DeadLetter(
                message=message,
                agent_id=agent_id,
                error=str(last_error) if last_error is not None else "unknown error",
                attempts=MAX_DELIVERY_ATTEMPTS,
            )
        )
        logger.error("agent_message_dead_lettered", agent_id=agent_id, message_id=message.id)
