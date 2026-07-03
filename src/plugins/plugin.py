"""The Plugin contract.

"Plugins communicate only through the Event Bus. No direct Core <-> Plugin
dependencies." (Phase 3 architecture decision.) A plugin therefore exposes
no synchronous, directly-callable method the Kernel or any core service
invokes — its only surface is `handle_event`, called by the PluginManager
when a subscribed event fires, and its only output channel is the
permissioned publish handle the PluginManager hands it at load time.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.core.events import Event
from src.plugins.manifest import PluginManifest


@runtime_checkable
class Plugin(Protocol):
    """Every plugin implements this, regardless of implementation language
    on the far side of a future non-Python transport (KERNEL_ARCHITECTURE_PROPOSAL.md
    §3a's polyglot-plugin note) — this Python Protocol is the in-process
    reference shape; a cross-language plugin would satisfy the same shape
    over serialized messages instead of a Python import.
    """

    @property
    def manifest(self) -> PluginManifest: ...

    async def on_load(self, publish: PluginPublishHandle) -> None:
        """Called once by the PluginManager when the plugin is loaded.
        `publish` is the plugin's permission-scoped handle for emitting events.
        """
        ...

    async def on_unload(self) -> None:
        """Called once by the PluginManager when the plugin is unloaded."""
        ...

    async def handle_event(self, event: Event, publish: PluginPublishHandle) -> None:
        """Called for every event matching a subscription this plugin's
        manifest permits. Must not raise for control flow — exceptions are
        caught and counted toward quarantine by the PluginManager, not
        propagated to other plugins or the Kernel.
        """
        ...


class PluginPublishHandle(Protocol):
    """A plugin's only way to emit events — permission-checked per manifest."""

    async def publish(self, event_name: str, payload: dict[str, object] | None = None) -> None: ...
