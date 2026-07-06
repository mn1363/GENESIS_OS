"""Unit tests for src/runtime/agents/communication.py."""

from __future__ import annotations

import pytest
from src.core.events import EventBus
from src.runtime.agents.communication import (
    MAX_DELIVERY_ATTEMPTS,
    AgentAlreadySubscribedError,
    AgentCommunicationBus,
    AgentMessage,
    AgentMessageType,
)


def _bus() -> AgentCommunicationBus:
    return AgentCommunicationBus(EventBus())


async def test_targeted_message_delivered_only_to_receiver() -> None:
    comm = _bus()
    received_a: list[AgentMessage] = []
    received_b: list[AgentMessage] = []

    async def handler_a(message: AgentMessage) -> None:
        received_a.append(message)

    async def handler_b(message: AgentMessage) -> None:
        received_b.append(message)

    comm.subscribe("agent-a", handler_a)
    comm.subscribe("agent-b", handler_b)

    await comm.publish(
        AgentMessage(
            sender_id="agent-b", receiver_id="agent-a", message_type=AgentMessageType.COMMAND
        )
    )

    assert len(received_a) == 1
    assert received_b == []


async def test_broadcast_message_delivered_to_every_subscriber_except_sender() -> None:
    comm = _bus()
    received_a: list[AgentMessage] = []
    received_b: list[AgentMessage] = []

    async def handler_a(message: AgentMessage) -> None:
        received_a.append(message)

    async def handler_b(message: AgentMessage) -> None:
        received_b.append(message)

    comm.subscribe("agent-a", handler_a)
    comm.subscribe("agent-b", handler_b)

    await comm.broadcast("agent-a", AgentMessageType.EVENT, {"topic": "ping"})

    assert received_a == []  # sender doesn't receive its own broadcast
    assert len(received_b) == 1
    assert received_b[0].payload == {"topic": "ping"}


async def test_subscribe_duplicate_agent_id_raises() -> None:
    comm = _bus()

    async def handler(message: AgentMessage) -> None:
        pass

    comm.subscribe("agent-a", handler)
    with pytest.raises(AgentAlreadySubscribedError):
        comm.subscribe("agent-a", handler)


async def test_unsubscribe_stops_delivery() -> None:
    comm = _bus()
    received: list[AgentMessage] = []

    async def handler(message: AgentMessage) -> None:
        received.append(message)

    comm.subscribe("agent-a", handler)
    comm.unsubscribe("agent-a")

    await comm.publish(
        AgentMessage(
            sender_id="agent-b", receiver_id="agent-a", message_type=AgentMessageType.EVENT
        )
    )

    assert received == []


async def test_unsubscribe_unknown_agent_is_a_no_op() -> None:
    _bus().unsubscribe("does-not-exist")  # must not raise


async def test_correlated_returns_messages_sharing_a_correlation_id() -> None:
    comm = _bus()

    async def handler(message: AgentMessage) -> None:
        pass

    comm.subscribe("agent-a", handler)

    first = await comm.broadcast("x", AgentMessageType.EVENT, correlation_id="corr-1")
    second = AgentMessage(
        sender_id="y",
        message_type=AgentMessageType.RESPONSE,
        correlation_id="corr-1",
    )
    await comm.publish(second)
    await comm.broadcast("z", AgentMessageType.EVENT, correlation_id="corr-2")

    correlated = comm.correlated("corr-1")

    assert [m.id for m in correlated] == [first.id, second.id]


async def test_correlated_returns_empty_list_for_unknown_id() -> None:
    assert _bus().correlated("unknown") == []


async def test_failed_handler_is_retried_up_to_max_attempts_then_dead_lettered() -> None:
    comm = _bus()
    attempts: list[int] = []

    async def always_fails(message: AgentMessage) -> None:
        attempts.append(1)
        raise RuntimeError("boom")

    comm.subscribe("agent-a", always_fails)

    await comm.publish(
        AgentMessage(
            sender_id="agent-b", receiver_id="agent-a", message_type=AgentMessageType.COMMAND
        )
    )

    assert len(attempts) == MAX_DELIVERY_ATTEMPTS
    dead_letters = comm.dead_letters()
    assert len(dead_letters) == 1
    assert dead_letters[0].agent_id == "agent-a"
    assert dead_letters[0].attempts == MAX_DELIVERY_ATTEMPTS
    assert "boom" in dead_letters[0].error


async def test_handler_recovering_within_retry_budget_is_not_dead_lettered() -> None:
    comm = _bus()
    calls = {"count": 0}

    async def flaky(message: AgentMessage) -> None:
        calls["count"] += 1
        if calls["count"] < 2:
            raise RuntimeError("first attempt fails")

    comm.subscribe("agent-a", flaky)

    await comm.publish(
        AgentMessage(
            sender_id="agent-b", receiver_id="agent-a", message_type=AgentMessageType.COMMAND
        )
    )

    assert calls["count"] == 2
    assert comm.dead_letters() == []


async def test_dead_letters_returns_a_copy_not_the_live_list() -> None:
    comm = _bus()

    async def always_fails(message: AgentMessage) -> None:
        raise RuntimeError("boom")

    comm.subscribe("agent-a", always_fails)
    await comm.publish(
        AgentMessage(
            sender_id="agent-b", receiver_id="agent-a", message_type=AgentMessageType.COMMAND
        )
    )

    first = comm.dead_letters()
    assert len(first) == 1
    first.clear()  # tamper with the returned copy only

    assert len(comm.dead_letters()) == 1


def test_agent_message_round_trips_through_event_payload() -> None:
    original = AgentMessage(
        sender_id="a",
        receiver_id="b",
        message_type=AgentMessageType.RESPONSE,
        payload={"x": 1},
    )

    restored = AgentMessage.from_event_payload(original.to_event_payload())

    assert restored == original
