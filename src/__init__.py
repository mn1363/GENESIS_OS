"""GENESIS OS — core package.

Package layout (see /docs and ai_workspace/architecture_reports/ for the
architectural source of truth):

    core/         Sealed core: runtime kernel, contracts, identity (GEN-0000-0003).
    runtime/      Runtime engine: execution state machine, task orchestration
                  (Runtime_*_v1 docs).
    plugins/      Plugin loader/registry (Python-side loader for the polyglot
                  Plugin Interface; GEN-0016).
    plugin_sdk/   Base classes/templates for first-party Python plugins.
    api/          FastAPI REST/WebSocket layer (GEN-0020, Runtime_System_API_Gateway_v1).
    cli/          Typer CLI entry points.
    config/       Settings loading (pydantic-settings) — see .env.example.
    database/     SQLAlchemy models + migrations (SQLite dev / PostgreSQL prod).
    services/     Cross-cutting services (memory store, vector search via Qdrant,
                  cache via Redis).
    utils/        Shared utilities with no architectural ownership of their own.

No implementation logic lives here yet — this is the Phase 1 (Repository
Initialization) skeleton. Runtime Core implementation is Phase 2.
"""
