"""Unit tests for src/plugin_sdk/testing.py."""

from __future__ import annotations

import pytest
from src.core.events import Event
from src.plugin_sdk.base import BasePlugin
from src.plugin_sdk.decorators import on_event
from src.plugin_sdk.testing import FakePublishHandle, PluginTestHarness
from src.plugins.manager import PluginPermissionError
from src.plugins.manifest import PluginManifest, PluginPermissions, PluginType


def _manifest() -> PluginManifest:
    return PluginManifest(
        id="p1",
        version="1.0.0",
        type=PluginType.UTILITY,
        permissions=PluginPermissions(subscribe=("task.completed",), publish=("plugin.custom",)),
    )


class GreeterPlugin(BasePlugin):
    @on_event("task.completed")
    async def handle_task_completed(self, event: Event, publish: object) -> None:
        await self.publish("plugin.custom", {"greeting": "hi"})


async def test_fake_publish_handle_records_permitted_publish() -> None:
    handle = FakePublishHandle(manifest=_manifest())
    await handle.publish("plugin.custom", {"x": 1})
    assert handle.published == [("plugin.custom", {"x": 1})]


async def test_fake_publish_handle_rejects_unpermitted_publish() -> None:
    handle = FakePublishHandle(manifest=_manifest())
    with pytest.raises(PluginPermissionError):
        await handle.publish("not.allowed", {})


async def test_harness_drives_full_plugin_lifecycle() -> None:
    plugin = GreeterPlugin(_manifest())
    harness = PluginTestHarness(plugin)

    await harness.load()
    await harness.fire(Event(name="task.completed", payload={}))

    assert harness.published == [("plugin.custom", {"greeting": "hi"})]

    await harness.unload()


async def test_harness_published_reflects_live_handle_state() -> None:
    plugin = GreeterPlugin(_manifest())
    harness = PluginTestHarness(plugin)
    await harness.load()

    assert harness.published == []

    await harness.fire(Event(name="task.completed", payload={}))
    assert harness.published == [("plugin.custom", {"greeting": "hi"})]
