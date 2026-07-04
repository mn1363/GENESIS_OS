"""Integration test: a `BasePlugin` subclass registered with the real
`PluginManager`/`EventBus` — not just the SDK's own test harness.

The SDK's contract is "produces something `Plugin`-shaped that
`PluginManager` accepts unmodified"; this is what actually proves that,
independent of `FakePublishHandle`/`PluginTestHarness` agreeing with
themselves.
"""

from __future__ import annotations

from src.core.events import Event, EventBus
from src.plugin_sdk.base import BasePlugin
from src.plugin_sdk.decorators import on_event
from src.plugins.manager import PluginManager
from src.plugins.manifest import PluginManifest, PluginPermissions, PluginType
from src.plugins.plugin import Plugin, PluginPublishHandle


class CounterPlugin(BasePlugin):
    def __init__(self, manifest: PluginManifest) -> None:
        super().__init__(manifest)
        self.count = 0

    @on_event("task.completed")
    async def handle_task_completed(self, event: Event, publish: PluginPublishHandle) -> None:
        self.count += 1
        await self.publish("plugin.custom", {"count": self.count})


def _manifest() -> PluginManifest:
    return PluginManifest(
        id="counter",
        version="1.0.0",
        type=PluginType.UTILITY,
        permissions=PluginPermissions(subscribe=("task.completed",), publish=("plugin.custom",)),
    )


async def test_base_plugin_satisfies_plugin_protocol() -> None:
    assert isinstance(CounterPlugin(_manifest()), Plugin)


async def test_base_plugin_subclass_works_under_the_real_plugin_manager() -> None:
    bus = EventBus()
    manager = PluginManager(bus)
    plugin = CounterPlugin(_manifest())

    received: list[dict[str, object]] = []

    async def _collect(event: Event) -> None:
        received.append(event.payload)

    bus.subscribe("plugin.custom", _collect)

    await manager.register_plugin(plugin)
    await bus.publish("task.completed", {"id": "t1"})
    await bus.publish("task.completed", {"id": "t2"})

    assert plugin.count == 2
    assert received == [{"count": 1}, {"count": 2}]
