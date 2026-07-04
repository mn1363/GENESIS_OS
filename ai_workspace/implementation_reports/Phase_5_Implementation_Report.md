# Phase 5 Implementation Report

**Scope:** Continuation from repository HEAD `3adf03c` ("Phase 4 -
Infrastructure Integration"). Two milestones this phase: the **Plugin SDK**
and the **Execution Engine** (GEN-0008), plus a repository-hygiene commit.
Each milestone landed as its own atomic commit; each ended with a full
`ruff check` / `ruff format --check` / `mypy --strict` / `pytest --cov`
pass before moving to the next.

---

## Milestone 0 — repository hygiene

**Audit finding:** `3adf03c` (the authoritative HEAD handed off for this
session) contained six `.rej` files (`src/storage/base.py.rej`,
`di_wire.py.rej`, `event_repository.py.rej`, `memory_repository.py.rej`,
`repositories.py.rej`, `task_repository.py.rej`, `requirements.txt.rej`)
and two `.patch` files committed at the repo root — debris from a prior
patch application where the target `.py` files themselves had already
applied correctly (verified: `ruff check`/`ruff format --check`/`mypy
--strict src`/`pytest` all passed on `3adf03c` before touching anything).
Removed the debris in its own commit; no functional code changed.

## Milestone 1 — Plugin SDK

**Audit finding:** `src/plugin_sdk/__init__.py` was a docstring-only stub —
its own docstring said "Implemented in Phase 4," though the actual Phase 4
delivered the Storage Layer instead. `src/plugins/` (Phase 3: `plugin.py`'s
`Plugin` Protocol, `manifest.py`, `manager.py`'s `PluginManager`) was
untouched and became the SDK's foundation, not something to rebuild.

Added, all in `src/plugin_sdk/`:
- **`base.py`** — `BasePlugin`, a concrete `Plugin` implementation to
  subclass instead of hand-writing the bare Protocol. Captures the
  `PluginPublishHandle` at `on_load()` for a `publish()` convenience method,
  and routes `handle_event()` to one method per event via `@on_event(...)`
  instead of a single growing if/elif chain.
- **`decorators.py`** — `@on_event(name)` attaches the event name to a
  handler method (via `setattr`, not a wrapper, so the method's own
  signature and identity are untouched); `BasePlugin._handlers()` scans the
  class for it.
- **`testing.py`** — `FakePublishHandle` re-enforces the exact same
  permission check and raises the same `PluginPermissionError` as
  `PluginManager`'s real handle (imported from `src.plugins.manager`, not
  reimplemented), so a plugin's own unit tests catch a permission bug the
  same way integration would. `PluginTestHarness` drives
  `on_load`/`handle_event`/`on_unload` without a live `PluginManager`/`EventBus`.

15 new tests (`tests/unit/plugin_sdk/`), 100% coverage on all three new
modules, including `test_integration.py` — a `BasePlugin` subclass
registered with the *real* `PluginManager`/`EventBus`, proving the SDK
produces something the manager accepts unmodified, not just something the
SDK's own fakes agree with.

## Milestone 2 — Execution Engine (GEN-0008)

**Audit finding, before writing anything:** `src/runtime/execution/`
already existed on disk with `models.py` (`ExecutionRequest`/
`ExecutionResponse`/`ExecutionMode`/`ExecutionStatus`) and `provider.py`
(the `ProviderAdapter` Protocol: `provider_id`, `health_check()`, `run()`)
— untracked, evidently scaffolded but never committed. `tests/unit/runtime/
execution/__init__.py` existed too, empty. No `engine.py`, no concrete
provider, no tests. Built on top of this scaffold exactly as found —
`ProviderAdapter.run()` (not `execute()`), `ExecutionStatus.SUCCESS` (not
`SUCCEEDED`), `ExecutionResponse.request_id`/`retry_count` (not
`execution_id`/`retries`) — rather than introducing a second, incompatible
naming scheme.

`src/runtime/agents/executor.py`'s own module docstring flagged the gap
directly: *"there is no real AI Execution Engine yet (GEN-0008, later
phase). This class exists to prove the multi-agent coordination pattern...
not to do real work."* That is what this milestone closes.

Added:
- **`providers/local_echo.py`** — `LocalEchoProvider`, a deterministic,
  in-process `ProviderAdapter` (GEN-0008's "Local Models"/"Offline Engines"
  categories) — no credentials, no network, always available. Exists so
  `ExecutionEngine` has a real provider to dispatch to; a remote-AI adapter
  is later-phase work, added the same way (implement `ProviderAdapter`,
  hand it to `ExecutionEngine`, nothing else changes).
- **`engine.py`** — `ExecutionEngine`, consolidating GEN-0008's Execution
  Dispatcher + Provider Manager + Retry Manager + Execution Monitor +
  Response Normalizer into one class rather than five: for one process
  with no distributed queue yet, five separate classes would be
  unexercised abstraction, not a feature. Retry policy: retry the same
  provider up to `max_retries_per_provider` times, then fail over to the
  next registered provider in order ("Provider Selection" = "first
  success wins," not cost/latency ranking — `ProviderAdapter.health_check()`
  is defined for that future refinement but not consulted yet); if every
  provider is exhausted, returns a `FAILED` `ExecutionResponse` rather than
  raising (GEN-0008's "Escalate to Kernel" — the caller decides what to do
  next, the engine doesn't crash the caller).
- **`src/runtime/agents/executor.py`** (modified, not replaced) —
  `ExecutorAgent` now takes an optional `engine: ExecutionEngine | None`,
  defaulting to `ExecutionEngine([LocalEchoProvider()])` if omitted, so
  `ExecutorAgent(event_bus)` — the existing call shape, unchanged — still
  works for every prior caller and test. The inline
  `f"stub output for: {description}"` is gone; `execute()` now builds a
  real `ExecutionRequest`, dispatches through the engine, and maps
  `ExecutionStatus.SUCCESS`/`FAILED` to the same `"executed"`/`"failed"`
  result shape `CriticAgent` and the existing tests already expect.

25 new/updated tests: `tests/unit/runtime/execution/` (`test_models.py`,
`test_local_echo.py`, `test_engine.py` — provider failover and retry
exhaustion both covered) plus four new cases added to the existing
`tests/unit/runtime/test_agents.py` (default engine, injected engine,
engine-failure status mapping) alongside the five pre-existing agent tests,
all of which still pass unmodified. 100% coverage on every new
`src/runtime/execution/*.py` module.

## Verification (both milestones, final state)

```
ruff check .          — All checks passed
ruff format --check . — 85 files already formatted
mypy --strict src     — Success: no issues found in 53 source files
mypy --strict (plugin_sdk/plugins/storage/runtime tests) — no issues, 21 files
pytest --cov=src      — 131 passed, 95% overall coverage
```

`git diff --stat -- src/core/` is empty for every commit this phase —
the sealed core was not touched.

The pre-existing `mypy --strict` failures in `tests/unit/core/
test_scheduler.py`/`test_kernel.py`/`test_tasks.py` (21 errors, unrelated
Phase 3 test files) remain untouched and out of this phase's scope, as
noted in the Phase 4 report.

## Known limitations / deviations

1. **`ExecutionEngine` provider selection is registration-order, not
   health/cost/latency-aware.** `ProviderAdapter.health_check()` exists in
   the Protocol for this but isn't called by the engine yet — there's only
   one provider today, so ranking logic would be unexercised. Documented as
   a TODO, not a silent gap.
2. **No real remote-AI `ProviderAdapter` exists yet.** `LocalEchoProvider`
   is deliberately the only one — GEN-0008's "Cloud Providers" category is
   later-phase work once there's a concrete provider (and credentials) to
   integrate against.
3. **`PluginManager` (Phase 3) still isn't wired into the Kernel's
   `DIContainer`**, the same standing note from the Phase 2/3/4 reports.
   Out of scope for both of this phase's milestones.

## Remaining TODOs (for a later phase)

- A real remote-AI `ProviderAdapter` (e.g. wrapping the Anthropic API),
  once GEN-0008's "Cloud Providers" category has a concrete target.
- Health/cost/latency-based provider ranking in `ExecutionEngine`, once a
  second provider exists to rank against the first.
- `PlannerAgent`'s decomposition and `CriticAgent`'s evaluation are both
  still Phase 3 stubs (GEN-0032 Task Decomposition Engine, GEN-0009 Quality
  Engine) — untouched this phase, since the task was the Execution Engine
  specifically, not the other two agents.
- Wire `PluginManager` and `wire_storage()` into one shared Kernel boot
  path (`scripts/run_kernel.py` currently only wires storage).

## Git commits (this phase)

```
chore: remove stray .rej/.patch debris from prior patch application
Phase 5 - Plugin SDK: BasePlugin, @on_event routing, test harness
Phase 5 - Execution Engine: ExecutionEngine, LocalEchoProvider, ExecutorAgent wiring
```
