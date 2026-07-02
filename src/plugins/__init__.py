"""Plugin Manager (Python-side loader/registry).

Loads and supervises plugins over the official Plugin Interface
(Runtime_Plugin_Interface_Standard_v1). Plugins communicate with the Core
exclusively through this boundary — the Core never imports plugin code
directly, so plugins may be implemented in any language. Implemented in
Phase 3.
"""
