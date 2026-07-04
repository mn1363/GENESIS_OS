"""Testing harness for plugin authors.

`PluginManager` (`src.plugins.manager`) is the only real, permission-enforcing
`PluginPublishHandle` implementation, but it requires a live `EventBus` and
registers real subscriptions — more than a plugin's own unit tests usually
need. `FakePublishHandle` reuses the exact same permission check
(`PluginManifest.permissions.allows_publish`, and raises the same
`PluginPermissionError` the real manager raises) without any of that
machinery, and `PluginTestHarness` drives a plugin's `Plugin` lifecycle
methods directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.events import Event
from src.plugins.manager import PluginPermissionError
from src.plugins.manifest import PluginManifest
from src.plugins.plugin import Plugin


@dataclass
class FakePublishHandle:
    """Records every `publish()` call instead of sending it anywhere.

    Enforces the plugin's own declared publish permissions, exactly like
    `PluginManager`'s real handle, so a permission bug is caught in a
    plugin's unit tests rather than first in integration.
    """

    manifest: PluginManifest
    published: list[tuple[str, dict[str, object] | None]] = field(default_factory=list)

    async def publish(self, event_name: str, payload: dict[str, object] | None = None) -> None:
        if not self.manifest.permissions.allows_publish(event_name):
            raise PluginPermissionError(
                f"Plugin {self.manifest.id} is not permitted to publish '{event_name}'"
            )
        self.published.append((event_name, payload))


class PluginTestHarness:
    """Drives a `Plugin`'s lifecycle for tests, without a `PluginManager`
    or `EventBus`.

    Usage::

        harness = PluginTestHarness(MyPlugin())
        await harness.load()
        await harness.fire(Event(name="task.completed", payload={}))
        assert harness.published == [("plugin.custom", {"ok": True})]
    """

    def __init__(self, plugin: Plugin) -> None:
        self.plugin = plugin
        self.handle = FakePublishHandle(manifest=plugin.manifest)

    async def load(self) -> None:
        await self.plugin.on_load(self.handle)

    async def unload(self) -> None:
        await self.plugin.on_unload()

    async def fire(self, event: Event) -> None:
        """Deliver `event` regardless of subscription permissions — a
        `PluginManager` would only ever call `handle_event` for events the
        manifest subscribes to, so this harness trusts the caller to pass a
        realistic event rather than re-implementing that gate."""
        await self.plugin.handle_event(event, self.handle)

    @property
    def published(self) -> list[tuple[str, dict[str, object] | None]]:
        return self.handle.published
