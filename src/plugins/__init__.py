"""Plugin Manager (Python-side loader/registry).

Loads and supervises plugins over the Event Bus (Phase 3 architecture
decision: plugins communicate only through events, no direct Core<->Plugin
dependency). The Core never imports plugin code directly, so plugins may
be implemented in any language in a future cross-language transport.
"""

from src.plugins.manager import (
    DuplicatePluginError,
    PluginManager,
    PluginPermissionError,
    PluginState,
)
from src.plugins.manifest import PluginManifest, PluginPermissions, PluginType
from src.plugins.plugin import Plugin, PluginPublishHandle

__all__ = [
    "Plugin",
    "PluginPublishHandle",
    "PluginManifest",
    "PluginPermissions",
    "PluginType",
    "PluginManager",
    "PluginState",
    "PluginPermissionError",
    "DuplicatePluginError",
]
