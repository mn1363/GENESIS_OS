# Phase 3 — Plugin System and Multi-Agent Foundation Implementation Report

**Scope (per approved Phase 3 decisions):** Event-Driven Plugin System, Hybrid Memory (interfaces + reference implementations only, no production storage), Multi-Agent Foundation (Planner/Executor/Critic coordinating only through the Kernel Scheduler and Event Bus). `src/core/` (the sealed Kernel from Phase 2) was not modified — verified below.

---

## Files created

**Plugin System (`src/plugins/`)**
- `manifest.py` — `PluginType`, `PluginPermissions` (subscribe/publish allow-lists), `PluginManifest`
- `plugin.py` — `Plugin` Protocol (`manifest`, `on_load`, `on_unload`, `handle_event`), `PluginPublishHandle` Protocol
- `manager.py` — `PluginManager`: implements the Kernel `Service` protocol; `register_plugin()`/`unregister_plugin()` (loading/lifecycle), `_PermissionedPublishHandle` (permission enforcement — a plugin publishing outside its manifest raises `PluginPermissionError`), consecutive-failure quarantine (isolation — a failing plugin is disabled after N failures without affecting other plugins or the Kernel)

**Hybrid Memory (`src/services/memory/`)**
- `interfaces.py` — `ShortTermMemory`, `VectorMemory` (the Qdrant abstraction), `KnowledgeGraph` Protocols; `VectorMatch`, `GraphNode`, `GraphEdge` value types
- `in_memory.py` — `InMemoryShortTermMemory`, `InMemoryVectorMemory` (brute-force cosine similarity), `InMemoryKnowledgeGraph` — explicitly labeled reference/test-double implementations, not production storage
- `service.py` — `MemoryService`: wraps the three interfaces, exposes 7 capabilities (`memory.short_term.get/set@v1`, `memory.vector.upsert/search@v1`, `memory.graph.add_node/add_edge/neighbors@v1`)

**Multi-Agent Foundation (`src/runtime/agents/`)**
- `base.py` — `AgentServiceBase` (shared `Service` protocol boilerplate)
- `models.py` — `Plan`, `PlanStep`
- `planner.py` — `PlannerAgent`: exposes `agent.plan@v1`; decomposes a goal (Phase 3 stub: one step) and submits each step via an injected `submit_task_fn` — never calls `ExecutorAgent` directly
- `executor.py` — `ExecutorAgent`: exposes `agent.execute@v1`; stub execution, publishes `agent.execution.completed`
- `critic.py` — `CriticAgent`: subscribes to `agent.execution.completed` in its own `start()`, publishes `agent.critique.completed`; also exposes `agent.critique@v1` for direct synchronous use

**Tests**
- `tests/unit/plugins/test_manager.py` (8 tests) — load/subscribe, duplicate rejection, unsubscribed-event isolation, unload, permission enforcement, quarantine after repeated failures, cross-plugin failure isolation, `stop()` unregisters all
- `tests/unit/services/test_memory.py` (5 tests) — short-term get/set/clear, vector similarity ordering, vector delete, graph neighbors, `MemoryService` capability-handler roundtrip
- `tests/unit/runtime/test_agents.py` (5 tests) — executor publishes completion event, critic reacts to the event, critic fails on empty output, planner submits via the injected scheduler function (not a direct call), full Planner→Executor→Critic flow using only Kernel-style primitives (fake `submit_task` + real `EventBus`)

Total: 14 implementation files, 6 test files (3 new packages), ~831 lines of new source.

## Files modified

- `src/plugins/__init__.py`, `src/services/memory/__init__.py` (newly populated), `src/runtime/agents/__init__.py` — public API exports for the new packages
- `src/core/*` — **not modified.** Verified: `git diff --stat` (below) shows zero changes under `src/core/`.

## Sealed-core verification

```
$ git diff --stat -- src/core/
(no output — zero files changed under src/core/ since Phase 2's commit)
```

The Kernel Scheduler, Capability Registry, Service Registry, Event Bus, and dispatch logic from `KERNEL_ARCHITECTURE_PROPOSAL.md` are used exactly as they were at the end of Phase 2 — Phase 3 components consume `src/core`'s public API (`Kernel.register_service`, `Kernel.submit_task`, `Kernel.events`) and add nothing to it.

## How the three architecture decisions are actually enforced (not just followed by convention)

1. **"No direct Core↔Plugin dependencies"** — a `Plugin` never receives the Kernel, `ServiceRegistry`, or `CapabilityRegistry`. It receives only a `PluginPublishHandle` scoped to its own manifest's `publish` permissions. There is no code path from a `Plugin` implementation back into `src/core` internals.
2. **"Plugins communicate only through the Event Bus"** — `PluginManager` never exposes a plugin's methods as a Kernel capability; the only entrypoint into a plugin is `handle_event()`, called from an `EventBus` subscription. Verified by `test_plugin_does_not_receive_unsubscribed_events` and the permission tests.
3. **"Agents communicate through the Kernel Scheduler and Event Bus; the Kernel remains the only orchestration point"** — no file in `src/runtime/agents/` imports another agent's class. `PlannerAgent` holds an injected `submit_task_fn` (bound to `Kernel.submit_task` by whoever wires it up) and an `EventBus`; `CriticAgent` holds only an `EventBus`. `test_full_planner_executor_critic_flow_via_kernel_primitives_only` exercises the complete chain using nothing but those two primitives and asserts the coordination happens correctly with zero direct references between agents.

## Test summary

```
46 passed in 3.00s
```
(28 from Phase 2 + 18 new Phase 3 tests, run together with no failures.)

## Coverage summary

```
Name                             Stmts   Miss  Cover
------------------------------------------------------
src/plugins/manager.py              90      5    94%
src/plugins/manifest.py             24      0   100%
src/plugins/plugin.py               10      0   100%
src/runtime/agents/base.py          10      4    60%
src/runtime/agents/critic.py        18      0   100%
src/runtime/agents/executor.py      15      0   100%
src/runtime/agents/models.py        12      0   100%
src/runtime/agents/planner.py       23      0   100%
src/services/memory/in_memory.py    48      2    96%
src/services/memory/interfaces.py   25      0   100%
src/services/memory/service.py      37      4    89%
------------------------------------------------------
TOTAL (whole project)              871     78    91%
```

`agents/base.py`'s 60% reflects `start()`/`stop()`/`health_check()`/`on_failure()` no-ops that subclasses inherit but Phase 3 tests don't call in isolation (they're exercised indirectly through `CriticAgent.start()`, which overrides one of them). Not a gap in tested behavior, just unexercised trivial pass-throughs.

## Static analysis (project-wide, not just Phase 3 files)

```
ruff check          — All checks passed
ruff format --check — 48 files already formatted
mypy --strict        — Success: no issues found in 35 source files
```

## Known limitations

1. **Plugin discovery is programmatic only.** `PluginManager.register_plugin()` takes an already-constructed `Plugin` instance — there is no filesystem scanner, dynamic import, or cross-language IPC loader yet. `PROJECT_ROADMAP.md` Phase 3's "Plugin Loader" objective is satisfied at the API level (loading = `register_plugin()`), not at the "discover plugins on disk" level.
2. **No Dependency Resolver or Version Manager.** `PluginManifest.version` is captured but nothing checks plugin-to-plugin dependencies or Kernel-version compatibility (`GEN-0016`'s "Version Compatibility" principle). Two roadmap Phase 3 objectives are therefore only partially met — flagged, not silently skipped.
3. **Quarantine is failure-count only.** No automatic recovery/un-quarantine path exists; a quarantined plugin stays quarantined until process restart or manual `unregister_plugin`/`register_plugin` again.
4. **Memory is Phase 3 scope exactly as decided: interfaces + in-memory reference implementations, no production backend.** `InMemoryVectorMemory` is brute-force (no ANN index) and will not scale — that's expected; it exists to make the `VectorMemory` Protocol testable, not to be used in production.
5. **Agents are coordination-pattern proofs, not real intelligence.** `PlannerAgent._decompose()` always produces exactly one step; `ExecutorAgent.execute()` returns a stub string; `CriticAgent._evaluate()` only checks for non-empty output. All three are explicitly documented in their module docstrings as Phase 3 stubs standing in for later-phase logic (GEN-0032 Task Decomposition, GEN-0008 Execution Engine, GEN-0009 Quality Engine).
6. **`DIContainer` (Phase 2) still isn't wired into service construction** — same known limitation carried over from the Phase 2 report; Phase 3 services are constructed and registered the same way Phase 2 services were.

## Remaining TODOs (for Phase 4+, not started)

- Filesystem/dynamic-import plugin discovery, and a cross-language (non-Python) plugin transport per `KERNEL_ARCHITECTURE_PROPOSAL.md`'s polyglot-plugin note.
- Plugin dependency resolution and Kernel-version compatibility checking.
- Real multi-step task decomposition for `PlannerAgent` (GEN-0032).
- Real execution logic for `ExecutorAgent`, once an AI Provider Abstraction (GEN-0034) exists to call.
- Real quality evaluation for `CriticAgent` (GEN-0009).
- Production `VectorMemory` backed by Qdrant, `ShortTermMemory` backed by Redis/DB, `KnowledgeGraph` backed by a real graph store — all substitutable behind the existing Protocols with no caller changes.

## Git commit

```
git add .
git commit -m "Phase 3 - Plugin System and Multi-Agent Foundation"
```

## Status

Phase 3 complete. Core remains sealed (verified, zero diff under `src/core/`). All requested checks (ruff, ruff format, mypy --strict, pytest) pass project-wide. Waiting for approval before Phase 4.
