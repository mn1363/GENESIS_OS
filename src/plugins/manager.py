"""Plugin Manager.

Responsible for loading, lifecycle, isolation, and permissions
(Phase 3 architecture decision) — the *only* component that talks to both
the Event Bus and a plugin instance. Plugins never receive the Kernel, the
Service Registry, or the Capability Registry; they receive a
permission-scoped `PluginPublishHandle` and nothing else, which is what
makes "no direct Core <-> Plugin dependencies" structural rather than a
convention.

Maps onto PROJECT_ROADMAP.md Phase 3 objectives:
    Plugin Registry   -> self._plugins / self.registered()
    Plugin Loader     -> register_plugin()
    Dependency Resolver -> not needed yet (no plugin declares dependencies
                            on other plugins in this foundation); a TODO,
                            not a silent omission — see Phase 3 report.
    Version Manager   -> manifest.version is captured and surfaced, but no
                          compatibility/semver resolution logic exists yet
                          (also a TODO).
    Plugin Isolation  -> quarantine after repeated handler failures, below.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

from src.core.events import Event, EventBus
from src.core.logging import get_logger
from src.plugins.manifest import PluginManifest
from src.plugins.plugin import Plugin

logger = get_logger(__name__)

DEFAULT_MAX_CONSECUTIVE_FAILURES = 3


class PluginState(StrEnum):
    LOADED = "loaded"
    QUARANTINED = "quarantined"
    UNLOADED = "unloaded"


class PluginPermissionError(RuntimeError):
    """Raised when a plugin attempts to publish/subscribe outside its manifest."""


class DuplicatePluginError(RuntimeError):
    pass


@dataclass
class _PluginRecord:
    plugin: Plugin
    manifest: PluginManifest
    state: PluginState = PluginState.LOADED
    consecutive_failures: int = 0


class _PermissionedPublishHandle:
    """The only object a plugin ever holds a reference to besides itself."""

    def __init__(self, manifest: PluginManifest, event_bus: EventBus) -> None:
        self._manifest = manifest
        self._event_bus = event_bus

    async def publish(self, event_name: str, payload: dict[str, object] | None = None) -> None:
        if not self._manifest.permissions.allows_publish(event_name):
            raise PluginPermissionError(
                f"Plugin {self._manifest.id} is not permitted to publish '{event_name}'"
            )
        await self._event_bus.publish(event_name, payload)


class PluginManager:
    """Implements the Kernel `Service` protocol so it can be registered
    like any other service, but never receives dispatched capability calls
    from plugins — only the Event Bus connects the two, per the Phase 3
    "Plugins communicate only through the Event Bus" decision.
    """

    def __init__(
        self, event_bus: EventBus, max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_FAILURES
    ) -> None:
        self._event_bus = event_bus
        self._max_consecutive_failures = max_consecutive_failures
        self._plugins: dict[str, _PluginRecord] = {}

    # ---- Service protocol (manager's own lifecycle as a Kernel service) --------------

    async def start(self) -> None:
        logger.info("plugin_manager_started")

    async def stop(self) -> None:
        for plugin_id in list(self._plugins):
            await self.unregister_plugin(plugin_id)
        logger.info("plugin_manager_stopped")

    async def health_check(self) -> bool:
        return True

    async def on_failure(self, error: BaseException) -> None:
        logger.error("plugin_manager_failure", error=str(error))

    # ---- Loading / lifecycle ------------------------------------------------------------

    async def register_plugin(self, plugin: Plugin) -> None:
        manifest = plugin.manifest
        if manifest.id in self._plugins:
            raise DuplicatePluginError(f"Plugin already registered: {manifest.id}")

        record = _PluginRecord(plugin=plugin, manifest=manifest)
        self._plugins[manifest.id] = record

        handle = _PermissionedPublishHandle(manifest, self._event_bus)
        await plugin.on_load(handle)

        for event_name in manifest.permissions.subscribe:
            self._event_bus.subscribe(event_name, self._make_wrapped_handler(manifest.id))

        logger.info("plugin_registered", plugin_id=manifest.id, type=manifest.type)
        await self._event_bus.publish("plugin.registered", {"plugin_id": manifest.id})

    async def unregister_plugin(self, plugin_id: str) -> None:
        record = self._plugins.get(plugin_id)
        if record is None:
            return
        await record.plugin.on_unload()
        record.state = PluginState.UNLOADED
        del self._plugins[plugin_id]
        await self._event_bus.publish("plugin.unregistered", {"plugin_id": plugin_id})

    def registered(self) -> list[PluginManifest]:
        return [r.manifest for r in self._plugins.values()]

    def state_of(self, plugin_id: str) -> PluginState | None:
        record = self._plugins.get(plugin_id)
        return record.state if record else None

    # ---- Isolation --------------------------------------------------------------------

    def _make_wrapped_handler(self, plugin_id: str) -> Callable[[Event], Awaitable[None]]:
        async def _handler(event: Event) -> None:
            record = self._plugins.get(plugin_id)
            if record is None or record.state is not PluginState.LOADED:
                return  # quarantined or unloaded plugins never receive events
            if not record.manifest.permissions.allows_subscribe(event.name):
                return  # defense in depth; subscription was already permission-gated
            handle = _PermissionedPublishHandle(record.manifest, self._event_bus)
            try:
                await record.plugin.handle_event(event, handle)
                record.consecutive_failures = 0
            except Exception as exc:  # noqa: BLE001 - one plugin failure must not affect the Kernel
                record.consecutive_failures += 1
                logger.error(
                    "plugin_handler_error",
                    plugin_id=plugin_id,
                    event_name=event.name,
                    error=str(exc),
                    consecutive_failures=record.consecutive_failures,
                )
                if record.consecutive_failures >= self._max_consecutive_failures:
                    record.state = PluginState.QUARANTINED
                    logger.error("plugin_quarantined", plugin_id=plugin_id)
                    await self._event_bus.publish("plugin.quarantined", {"plugin_id": plugin_id})

        return _handler
