"""Unit tests for src/plugin_sdk/base.py."""

from __future__ import annotations

import pytest
from src.core.events import Event
from src.plugin_sdk.base import BasePlugin, PluginNotLoadedError
from src.plugin_sdk.decorators import on_event
from src.plugin_sdk.testing import FakePublishHandle
from src.plugins.manifest import PluginManifest, PluginPermissions, PluginType


def _manifest(
    plugin_id: str = "p1",
    subscribe: tuple[str, ...] = ("task.completed",),
    publish: tuple[str, ...] = ("plugin.custom",),
) -> PluginManifest:
    return PluginManifest(
        id=plugin_id,
        version="1.0.0",
        type=PluginType.UTILITY,
        permissions=PluginPermissions(subscribe=subscribe, publish=publish),
    )


class EchoPlugin(BasePlugin):
    def __init__(self, manifest: PluginManifest) -> None:
        super().__init__(manifest)
        self.received: list[str] = []

    @on_event("task.completed")
    async def handle_task_completed(self, event: Event, publish: object) -> None:
        self.received.append(event.name)
        await self.publish("plugin.custom", {"task_id": event.payload.get("id")})


async def test_manifest_property_returns_constructor_manifest() -> None:
    manifest = _manifest()
    plugin = EchoPlugin(manifest)
    assert plugin.manifest is manifest


async def test_handle_event_routes_to_decorated_method() -> None:
    plugin = EchoPlugin(_manifest())
    handle = FakePublishHandle(manifest=plugin.manifest)
    await plugin.on_load(handle)

    await plugin.handle_event(Event(name="task.completed", payload={"id": "t1"}), handle)

    assert plugin.received == ["task.completed"]
    assert handle.published == [("plugin.custom", {"task_id": "t1"})]


async def test_handle_event_ignores_events_with_no_registered_handler() -> None:
    plugin = EchoPlugin(_manifest())
    handle = FakePublishHandle(manifest=plugin.manifest)
    await plugin.on_load(handle)

    await plugin.handle_event(Event(name="unrelated.event", payload={}), handle)

    assert plugin.received == []


async def test_publish_before_on_load_raises() -> None:
    plugin = EchoPlugin(_manifest())
    with pytest.raises(PluginNotLoadedError):
        await plugin.publish("plugin.custom", {})


async def test_on_unload_clears_publish_handle() -> None:
    plugin = EchoPlugin(_manifest())
    handle = FakePublishHandle(manifest=plugin.manifest)
    await plugin.on_load(handle)
    await plugin.on_unload()

    with pytest.raises(PluginNotLoadedError):
        await plugin.publish("plugin.custom", {})


async def test_two_plugin_instances_do_not_share_publish_handle_state() -> None:
    """Regression guard: `_publish` must be instance state, not accidentally
    shared via a class-level default."""
    handle_a = FakePublishHandle(manifest=_manifest("a"))
    handle_b = FakePublishHandle(manifest=_manifest("b"))
    plugin_a = EchoPlugin(_manifest("a"))
    plugin_b = EchoPlugin(_manifest("b"))

    await plugin_a.on_load(handle_a)

    with pytest.raises(PluginNotLoadedError):
        await plugin_b.publish("plugin.custom", {})
    await plugin_b.on_load(handle_b)
    await plugin_b.publish("plugin.custom", {})
    assert handle_a.published == []
    assert handle_b.published == [("plugin.custom", {})]
