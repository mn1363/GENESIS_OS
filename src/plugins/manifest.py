"""Plugin manifest — the declared contract a plugin registers with.

Structure adapted from GEN-0016_Plugin_Architecture.md and
GENESIS_OS_Runtime_Plugin_Interface_Standard_v1.md's Plugin {id, version,
type, permissions, ...} shape, adapted for the Phase 3 architecture
decision: plugins communicate only through the Event Bus, so `execute()`
is replaced by declared publish/subscribe permissions rather than a
directly-callable entrypoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class PluginType(StrEnum):
    """Runtime_Plugin_Interface_Standard_v1.md's allowed plugin types."""

    DATA = "data_plugin"
    AI = "ai_plugin"
    AUTOMATION = "automation_plugin"
    SIMULATION = "simulation_plugin"
    UTILITY = "utility_plugin"


@dataclass(frozen=True)
class PluginPermissions:
    """Event names (or "*") a plugin is allowed to publish/subscribe to.

    Enforced by PluginManager, not self-reported by the plugin at runtime —
    see manager.py's PermissionedEventBusHandle.
    """

    subscribe: tuple[str, ...] = field(default_factory=tuple)
    publish: tuple[str, ...] = field(default_factory=tuple)

    def allows_subscribe(self, event_name: str) -> bool:
        return "*" in self.subscribe or event_name in self.subscribe

    def allows_publish(self, event_name: str) -> bool:
        return "*" in self.publish or event_name in self.publish


@dataclass(frozen=True)
class PluginManifest:
    """The declared, immutable-once-registered identity of a plugin."""

    id: str
    version: str
    type: PluginType
    permissions: PluginPermissions
    description: str = ""
