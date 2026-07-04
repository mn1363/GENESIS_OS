"""Plugin SDK — base classes and templates for first-party Python plugins.

Reference implementation of the Plugin Interface for plugin authors who
choose Python; not required by non-Python plugins. Implemented in Phase 5.

    base.py        -- BasePlugin: subclass instead of implementing the
                       bare Plugin Protocol by hand
    decorators.py  -- @on_event(name): route handle_event to one method
                       per event instead of an if/elif chain
    testing.py     -- FakePublishHandle + PluginTestHarness: unit-test a
                       plugin's on_load/handle_event/on_unload without a
                       live PluginManager or EventBus
"""
