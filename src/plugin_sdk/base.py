"""`BasePlugin` — the Plugin SDK's reference base class.

Implements `src.plugins.plugin.Plugin` so a plugin author subclasses this
instead of writing the bare Protocol from scratch: manifest storage,
`on_load`/`on_unload` bookkeeping, a `publish()` convenience bound to the
handle captured at load time, and per-event method routing via
`@on_event(...)` (`decorators.py`) instead of one large `handle_event`
if/elif chain.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast

from src.core.events import Event
from src.plugin_sdk.decorators import event_name_of
from src.plugins.manifest import PluginManifest
from src.plugins.plugin import PluginPublishHandle

_EventHandler = Callable[["BasePlugin", Event, PluginPublishHandle], Awaitable[None]]


class PluginNotLoadedError(RuntimeError):
    """Raised by `BasePlugin.publish()` before `on_load()` has run."""


class BasePlugin:
    """Reference `Plugin` implementation for Python plugin authors.

    Subclass and decorate handler methods with `@on_event("name")`;
    `handle_event` dispatches automatically. Override `on_load`/`on_unload`
    only if setup/teardown beyond capturing the publish handle is needed —
    call `await super().on_load(publish)` first if you do.
    """

    def __init__(self, manifest: PluginManifest) -> None:
        self._manifest = manifest
        self._publish: PluginPublishHandle | None = None

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    async def on_load(self, publish: PluginPublishHandle) -> None:
        self._publish = publish

    async def on_unload(self) -> None:
        self._publish = None

    async def handle_event(self, event: Event, publish: PluginPublishHandle) -> None:
        handler = self._handlers().get(event.name)
        if handler is not None:
            await handler(self, event, publish)

    async def publish(self, event_name: str, payload: dict[str, object] | None = None) -> None:
        """Publish through the handle captured at `on_load` — for use inside
        handler methods, so they don't need to thread `publish` through
        every call. Raises `PluginNotLoadedError` before `on_load()` runs.
        """
        if self._publish is None:
            raise PluginNotLoadedError(f"Plugin {self.manifest.id} is not loaded")
        await self._publish.publish(event_name, payload)

    @classmethod
    def _handlers(cls) -> dict[str, _EventHandler]:
        handlers: dict[str, _EventHandler] = {}
        for name in dir(cls):
            if name.startswith("__"):
                continue
            attr = getattr(cls, name, None)
            event_name = event_name_of(attr) if callable(attr) else None
            if event_name is not None:
                handlers[event_name] = cast(_EventHandler, attr)
        return handlers
