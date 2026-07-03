"""Unit tests for src/plugins/manager.py."""

from __future__ import annotations

import pytest
from src.core.events import Event, EventBus
from src.plugins.manager import (
    DuplicatePluginError,
    PluginManager,
    PluginPermissionError,
    PluginState,
)
from src.plugins.manifest import PluginManifest, PluginPermissions, PluginType
from src.plugins.plugin import PluginPublishHandle

pytestmark = pytest.mark.asyncio


class RecordingPlugin:
    def __init__(self, manifest: PluginManifest) -> None:
        self._manifest = manifest
        self.loaded = False
        self.unloaded = False
        self.events_received: list[str] = []
        self.raise_on_event = False
        self._publish: PluginPublishHandle | None = None

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    async def on_load(self, publish: PluginPublishHandle) -> None:
        self.loaded = True
        self._publish = publish

    async def on_unload(self) -> None:
        self.unloaded = True

    async def handle_event(self, event: Event, publish: PluginPublishHandle) -> None:
        if self.raise_on_event:
            raise ValueError("plugin failure")
        self.events_received.append(event.name)


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


async def test_register_plugin_calls_on_load_and_subscribes() -> None:
    bus = EventBus()
    manager = PluginManager(bus)
    plugin = RecordingPlugin(_manifest())

    await manager.register_plugin(plugin)
    assert plugin.loaded
    assert manager.state_of("p1") == PluginState.LOADED

    await bus.publish("task.completed", {"x": 1})
    assert plugin.events_received == ["task.completed"]


async def test_register_duplicate_plugin_raises() -> None:
    bus = EventBus()
    manager = PluginManager(bus)
    await manager.register_plugin(RecordingPlugin(_manifest()))
    with pytest.raises(DuplicatePluginError):
        await manager.register_plugin(RecordingPlugin(_manifest()))


async def test_plugin_does_not_receive_unsubscribed_events() -> None:
    bus = EventBus()
    manager = PluginManager(bus)
    plugin = RecordingPlugin(_manifest(subscribe=("task.completed",)))
    await manager.register_plugin(plugin)

    await bus.publish("task.failed", {})
    assert plugin.events_received == []


async def test_unregister_calls_on_unload_and_stops_events() -> None:
    bus = EventBus()
    manager = PluginManager(bus)
    plugin = RecordingPlugin(_manifest())
    await manager.register_plugin(plugin)

    await manager.unregister_plugin("p1")
    assert plugin.unloaded
    assert manager.state_of("p1") is None

    await bus.publish("task.completed", {})
    assert plugin.events_received == []  # already unregistered, no longer subscribed


async def test_publish_outside_permission_raises() -> None:
    bus = EventBus()
    manager = PluginManager(bus)
    plugin = RecordingPlugin(_manifest(publish=("plugin.custom",)))
    await manager.register_plugin(plugin)
    assert plugin._publish is not None

    with pytest.raises(PluginPermissionError):
        await plugin._publish.publish("not.allowed", {})

    await plugin._publish.publish("plugin.custom", {})  # should not raise


async def test_repeated_failures_quarantine_plugin() -> None:
    bus = EventBus()
    manager = PluginManager(bus, max_consecutive_failures=2)
    plugin = RecordingPlugin(_manifest())
    plugin.raise_on_event = True
    await manager.register_plugin(plugin)

    await bus.publish("task.completed", {})
    assert manager.state_of("p1") == PluginState.LOADED
    await bus.publish("task.completed", {})
    assert manager.state_of("p1") == PluginState.QUARANTINED

    # further events must not reach a quarantined plugin
    plugin.raise_on_event = False
    await bus.publish("task.completed", {})
    assert plugin.events_received == []


async def test_one_plugin_failure_does_not_affect_another() -> None:
    bus = EventBus()
    manager = PluginManager(bus, max_consecutive_failures=1)
    bad = RecordingPlugin(_manifest(plugin_id="bad"))
    bad.raise_on_event = True
    good = RecordingPlugin(_manifest(plugin_id="good"))

    await manager.register_plugin(bad)
    await manager.register_plugin(good)

    await bus.publish("task.completed", {})
    assert manager.state_of("bad") == PluginState.QUARANTINED
    assert good.events_received == ["task.completed"]


async def test_stop_unregisters_all_plugins() -> None:
    bus = EventBus()
    manager = PluginManager(bus)
    plugin = RecordingPlugin(_manifest())
    await manager.register_plugin(plugin)

    await manager.stop()
    assert plugin.unloaded
    assert manager.registered() == []
