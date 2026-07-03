# KERNEL_ARCHITECTURE_PROPOSAL.md

**Status:** PROPOSAL — architecture only, no implementation. **Revision 3:** adds the Kernel Scheduler (task scheduling, priority, queueing, concurrency control, retry, timeout, pause/resume, cancellation) as the final architectural component before Phase 2 implementation.
**Fills the gap identified in** `Conflict_Report.md` §3 (`GEN-0004_Kernel_Architecture.md` is a corrupted duplicate of `GEN-0005_Memory_Architecture.md`; no real kernel spec exists in the corpus)
**Grounded in:** `GEN-0003_System_Architecture.md` (layered architecture, communication rules, state management), `GEN-0015_Event_System.md` (event lifecycle), `GENESIS_OS_Runtime_Execution_State_Machine_v1.md` (task state model), `GENESIS_OS_Runtime_Bootstrap_Application_Layer_v1.md` (bootstrap responsibilities), and the approved stack decision (Python 3.13 / FastAPI / SQLite–PostgreSQL / Qdrant / Redis, polyglot plugins over an IPC boundary).

This document defines the Runtime Kernel that `GEN-0003_System_Architecture.md` assumes exists ("GENESIS Kernel owns engineering decisions... Subsystems never communicate directly. Every communication passes through GENESIS Kernel") but never itself specifies.

---

## 1. Runtime Kernel responsibilities

Per `GEN-0003`'s communication and state-management rules, the Kernel is the **only** component permitted to:

1. Hold the system's canonical in-memory state (task registry, service registry, capability registry, active session context).
2. Route every inter-subsystem call **by capability, not by concrete service** — Planner, Memory, Agents, Quality, Execution never call each other directly, and callers never address a specific service by name; they request a capability, and the Kernel resolves it to whichever registered service currently provides that capability (see §3a).
3. Own the boot and shutdown sequence.
4. Own service lifecycle (start, stop, health, restart) for every registered subsystem.
5. Own the event bus (publish/subscribe dispatch — the transport mechanics are `GEN-0015`'s concern, but the Kernel owns *when* dispatch happens relative to task state).
6. Enforce the sealed-core boundary: the Kernel may load and call Runtime-layer and Plugin-layer code, but nothing in Runtime or Plugin layers may reach back into Kernel internals except through the published Kernel API.
7. Own **when and what** to execute, via the Kernel Scheduler (§3b) — the Execution Engine (Runtime layer, outside the sealed core) only ever executes what the Scheduler admits; it has no queue, priority, or concurrency logic of its own.

The Kernel explicitly does **not**: execute AI provider calls (Execution Engine's job), make planning decisions (Planner's job), or implement business logic for any subsystem. It is a coordinator, not a worker.

---

## 2. Module boundaries

```
┌─────────────────────────────────────────────────────────┐
│                      RUNTIME KERNEL                       │
│  (src/core/ — sealed, per README.md / GEN-0002)           │
│                                                             │
│   Service Registry │ Capability Registry │ Event Bus       │
│   Task State Store │ Kernel Scheduler    │ DI Container    │
│   Boot Sequencer   │ Shutdown Sequencer                     │
└─────────────────────────────────────────────────────────┘
        ▲                    ▲                    ▲
        │ Kernel API only    │ Kernel API only    │ Kernel API only
        │ (capability-       │ (capability-        │ (capability-
        │  addressed)        │  addressed)          │  addressed)
┌───────┴──────┐     ┌───────┴──────┐     ┌───────┴──────┐
│   Runtime     │     │   Services    │     │   Plugins     │
│ (Planner,     │     │ (Memory,      │     │ (loaded via   │
│  Agent        │     │  Vector       │     │  Plugin       │
│  Runtime,     │     │  Search,      │     │  Interface —  │
│  Execution,   │     │  Cache)       │     │  any language)│
│  Quality)     │     │               │     │               │
└───────────────┘     └───────────────┘     └───────────────┘
   each exposes ≥1 declared Capability, registered with the
   Capability Registry at service-registration time (§3a)
```

**Rule:** no arrow skips the Kernel. A module boundary is crossed only by calling a Kernel-exposed contract (an interface/protocol registered with the Kernel), never by importing another module's internals directly. This is enforceable in Python via package-level `__all__` restrictions and import-linter-style boundary checks in CI (tooling choice, not part of this architecture document).

---

## 3. Service registry

- Every subsystem (Planner, Memory, Agents, Quality, Execution Engine, and — at arm's length — Plugins) registers itself with the Kernel at boot as a **named service** implementing a declared contract (a Python `Protocol`).
- Registry entry = `{name, contract, instance, health_check, dependencies[], capabilities[]}` — the new `capabilities[]` field is what §3a is built on.
- The registry is the single lookup table the Kernel's dispatcher uses to route calls; it is not exposed for direct mutation by services — only the Kernel's registration API can add/remove entries.
- Plugins register through a **separate, restricted registry** (the Plugin Registry, owned by `src/plugins/`, itself a registered Kernel service) so a misbehaving plugin cannot pollute the core service registry.

---

## 3a. Capability Registry *(added per architect approval feedback)*

**The core idea:** the Kernel dispatches by *what a caller needs done*, not by *which concrete service happens to do it today*. This is a second registry, alongside the Service Registry, and it is what all Kernel dispatch (§5, §9) is actually addressed against.

- **Capability** = a named, versioned contract describing a unit of behavior the Kernel can dispatch — e.g. `planning.decompose_task@v1`, `memory.retrieve_context@v1`, `execution.run_step@v1`, `quality.validate_output@v1`. A capability is an interface, not an implementation.
- **Every registered Service must declare one or more Capabilities it provides** at registration time (§3's `capabilities[]` field). A service with zero declared capabilities cannot receive dispatched calls — it's inert from the Kernel's point of view.
- **Registry entry** = `{capability_name, version, provider_service, contract_schema}`. Multiple services *may* register the same capability (e.g. two different Execution Engine backends both providing `execution.run_step@v1`); the Kernel's dispatcher picks a provider using a resolution policy (default: single active provider per capability; a load-balanced or capability-priority policy is a future extension, not part of this proposal).
- **Callers request capabilities, never service names.** The Planner asking for prior context calls `Kernel.dispatch("memory.retrieve_context", ...)`, not `Kernel.call_service("Memory", ...)`. This indirection is the mechanism, not an implementation detail — it's what makes the rest of this section's stated goals possible:
  - **Multi-agent execution:** several Agent Runtime instances can each register `agent.execute@v1` under different agent identities; the Kernel dispatches to "an agent capable of X" without the caller needing to know how many agents exist or which one will handle it.
  - **AI orchestration:** swapping or adding a model/provider becomes "register a new provider for `execution.run_step@v1`," not a code change in every caller that currently hardcodes the Execution Engine.
  - **Polyglot plugins:** a plugin declares which capabilities it provides/needs in its manifest (Plugin Interface, Phase 3/4) using the same capability names as core services. The Kernel dispatch path is identical whether the capability is provided by Python core code or a plugin in another language — capability-addressing, not service-addressing, is what makes "the Core must never depend on plugin implementation languages" (approved architecture decision) actually hold at the dispatch layer, not just at the network/IPC layer.
- **Capability versioning:** capabilities are versioned (`@v1`, `@v2`) independently of their providing service's version, so a service can be upgraded internally without breaking callers, and a new capability version can be introduced alongside the old one during migration.
- **Relationship to the Service Registry:** the Service Registry answers "what is registered and is it healthy" (§8); the Capability Registry answers "who do I call for X" (dispatch). A service can be `HEALTHY` in the Service Registry but temporarily withdraw a capability (e.g. a degraded Qdrant-backed service withdrawing `memory.semantic_search@v1` while keeping `memory.retrieve_context@v1` available) — capability withdrawal is more granular than service failure.

---

## 3b. Kernel Scheduler *(added per architect approval feedback — final Kernel component)*

**Division of responsibility, stated exactly as directed:** the Scheduler decides *when and what* to execute; the Execution Engine (Runtime layer, `src/runtime/`) executes work once admitted. The Execution Engine has no queue, no priority logic, and no concurrency limits of its own — it is a pure worker the Scheduler calls via `dispatch("execution.run_step@v1", ...)` (§3a) once a task/step has been admitted to run.

The Scheduler is part of the Kernel (`src/core/`), not the Runtime layer, because admission control is a system-wide, cross-subsystem concern — it has to see every task competing for execution capacity regardless of which subsystem produced it (agent tasks, plugin-triggered tasks, scheduled/retried tasks all share one Scheduler), which matches `GEN-0003`'s "no subsystem owns global state" rule from §1.

Responsibilities, mapped onto the task state model from `GENESIS_OS_Runtime_Execution_State_Machine_v1.md`:

- **Task scheduling:** decides when a `QUEUED` task transitions to `EXECUTING` — i.e. when it's actually handed to `dispatch("execution.run_step@v1", ...)`. Nothing reaches `EXECUTING` except through the Scheduler.
- **Priority management:** each task carries a priority (declared at creation, adjustable while `QUEUED`). The Scheduler orders admission by priority, not FIFO-only; a fixed low-priority-starvation guard (age-based priority boost) is part of the policy, not left unspecified.
- **Queue management:** the Scheduler owns the `QUEUED` task queue — a persistence-backed queue (durable across restarts, per the Task State Store, §1), not just an in-memory list, so queued work survives a Kernel restart.
- **Concurrency control:** the Scheduler enforces a configurable max-concurrent-executions limit (global, and optionally per-capability — e.g. capping concurrent `execution.run_step@v1` calls separately from concurrent `memory.semantic_search@v1` calls) so the Kernel never over-subscribes a provider (especially relevant for rate-limited AI provider capabilities, `GEN-0034`).
- **Retry policy:** on a task reaching `FAILED`, the Scheduler — not the Execution Engine — decides whether to requeue (`RECOVERED`, per §8's retry/terminate branch), using a bounded-backoff policy (max attempts, exponential backoff) attached to the task at creation or defaulted per-capability.
- **Timeout management:** the Scheduler enforces a max-duration per `EXECUTING` task (default plus per-capability/per-task override) independent of the per-call timeout already enforced by Kernel dispatch (§5) — dispatch-timeout protects a single synchronous call; Scheduler-timeout protects the whole task's total executing time, which may span multiple dispatched calls.
- **Pause / Resume:** a `QUEUED` or `EXECUTING` task can be paused (Scheduler stops admitting/continuing it, without discarding its state) and later resumed from where the state machine left off. Pause is a Scheduler-level control, distinct from a task naturally finishing a step — this is required for capability-aware backpressure (§3a: a capability provider going `DEGRADED` can have the Scheduler pause tasks depending on it rather than letting them fail).
- **Task cancellation:** an explicit, caller-initiated transition of a `QUEUED` or `EXECUTING` task to `TERMINATED` (§8's task states) that the Scheduler is responsible for propagating — including signaling the Execution Engine to abort an in-flight step, not just refusing to admit further ones.

**Interaction with the Capability Registry (§3a):** the Scheduler decides *when* to call `dispatch(capability, ...)`; the Capability Registry decides *who* answers that call. The Scheduler never picks a concrete provider itself — that stays the Capability Registry's job, keeping the "swap providers without touching callers" property intact even under scheduling/backpressure logic.

---

## 4. Dependency injection strategy

- Constructor injection only — no service reaches into a global/singleton to fetch its dependencies; the Kernel resolves and passes them in at construction time. This matches `CODING_STANDARDS.md`'s "use dependency injection where appropriate" rule and keeps every module independently testable (`CODING_STANDARDS.md` general principles).
- The Kernel's DI container resolves the dependency graph declared in each service's registration (`dependencies: []` field in §3) at boot time, in dependency order (see §6). Circular dependencies between core services are a boot-time error, not a runtime failure.
- **Dependencies are declared and injected by capability, not by concrete service reference** — a service that depends on "something providing `memory.retrieve_context@v1`" receives a Kernel-resolved capability handle, not a direct reference to the Memory service class. This keeps the DI graph consistent with capability-based dispatch (§3a): swapping which service backs a capability never requires touching a dependent service's injected references.
- Plugins receive a narrow, capability-scoped injected handle (the Plugin Runtime API) rather than the full DI graph — a plugin never receives a direct reference to another service, only to the Kernel-mediated interface for the capabilities it declared needing.

---

## 5. Internal communication

Two channels, used for different purposes — this distinction is the main design decision this document adds on top of `GEN-0015`:

1. **Synchronous request/response (Kernel dispatch):** used when a subsystem needs an answer before proceeding (e.g. Planner asking for `memory.retrieve_context@v1` before producing a plan). Implemented as a Kernel-mediated call **addressed by capability name, resolved through the Capability Registry (§3a) to a concrete provider** — never a direct call against a named service. Kernel enforces a timeout per call.
2. **Asynchronous events (Event Bus, per `GEN-0015`):** used for everything that doesn't need an immediate answer — task state transitions, audit/log events, plugin notifications. Publishers never know who (if anyone) is subscribed. Events are immutable and archived per `GEN-0015`'s Observable/Replayable principles, backed by Redis (approved stack) for pub/sub transport and the relational store for the durable event log.

Plugins **only ever use channel 2** (events) plus a narrow RPC surface exposed by the Plugin Interface — they are never given access to the synchronous Kernel dispatch used internally by core services. This is what makes the "any language" polyglot plugin rule from the architecture decision safe: a plugin's only contract with the Kernel is a serializable message format, so implementation language is invisible to the Kernel.

---

## 6. Boot sequence

```
1. Load configuration (src/config/ — env vars, .env, per GEN-0017)
2. Initialize structured logging
3. Open infrastructure connections:
     a. Database (SQLite dev / PostgreSQL prod)
     b. Redis (cache + event transport)
     c. Qdrant (vector memory) — deferred/lazy if unavailable, logged as degraded, not fatal
4. Construct the Kernel (Service Registry, Capability Registry, Event Bus, Task State Store, Kernel Scheduler, DI Container)
5. Register core services in dependency order, **each registration also publishing its declared capabilities to the Capability Registry**:
     Memory → Context Engine → Planner → Agent Runtime → Execution Engine → Quality Engine
     (this order matches GEN-0003's component list and their natural data dependency:
      nothing can plan or execute without memory/context available first)
6. Run each service's async health check; a failed mandatory service aborts boot
   (fail-fast, per BUILD_INSTRUCTION.md "detect failures... isolate failures")
7. Load Plugin Registry (src/plugins/) and discover/register declared plugins,
   **registering each plugin's declared capabilities into the same Capability Registry**
   (plugin load failures are isolated — a broken plugin logs and is skipped,
   never aborts boot; core boot must not depend on third-party code)
8. Start API layer (FastAPI) and/or CLI (Typer) as the process entrypoint
9. Emit `system.boot.completed` event
10. Kernel enters ready state, accepts requests
```

---

## 7. Shutdown sequence

Reverse of boot, with draining:

```
1. Emit `system.shutdown.requested` event
2. Stop accepting new external requests (API/CLI layer)
3. Drain in-flight tasks: the Scheduler stops admitting new `QUEUED→EXECUTING` transitions
   and allows already-`EXECUTING` tasks to reach a safe checkpoint
   (bounded by a shutdown grace period; tasks not finished in time are
   transitioned to FAILED with a "shutdown" reason, per the state model in §8;
   still-`QUEUED` tasks remain queued in the persisted queue for the next boot)
4. Unregister and stop services in reverse dependency order:
     Quality Engine → Execution Engine → Agent Runtime → Planner → Context Engine → Memory
5. Flush event bus / ensure durable event log is written
6. Close infrastructure connections (Qdrant, Redis, Database)
7. Emit `system.shutdown.completed` (best-effort — transport may already be closing)
8. Process exit
```

---

## 8. Service lifecycle & failure recovery

Each registered service exposes a small lifecycle contract: `start()`, `stop()`, `health_check()`, `on_failure(error)`.

Service states: `REGISTERED → STARTING → HEALTHY → (DEGRADED ⇄ HEALTHY) → STOPPING → STOPPED`, with a `FAILED` state reachable from any of `STARTING`/`HEALTHY`/`DEGRADED`.

Failure recovery policy (per `BUILD_INSTRUCTION.md` §Error Handling: detect, isolate, recover where possible, structured logs):

- **Mandatory services** (Memory, Planner, Agent Runtime, Execution Engine, Quality Engine): failure during boot aborts startup. Failure at runtime marks the service `FAILED`, the Kernel stops routing to it, in-flight tasks depending on it transition to `FAILED` (see task state model below), and the Kernel attempts one bounded restart with backoff before surfacing a system-level degraded alert.
- **Optional services** (Qdrant vector memory, Redis cache): failure marks the service `DEGRADED`, not `FAILED` — the Kernel continues operating with reduced capability (e.g. no semantic search) and logs the degradation. This matches the approved stack's dev/prod split, where local dev may not always have Qdrant/Redis running.
- **Plugins**: failure is always isolated to the plugin. The Kernel never restarts a plugin automatically (plugin restart policy is a Plugin Manager concern, Phase 3) and a plugin failure never marks a core service `FAILED`.

Task-level failure recovery reuses the state model already defined in `GENESIS_OS_Runtime_Execution_State_Machine_v1.md`: `CREATED → VALIDATED → PLANNED → QUEUED → EXECUTING → POST_PROCESSING → COMPLETED`, with a `FAILED → (RECOVERED | TERMINATED)` branch. The Kernel Scheduler (§3b) is the component that owns transitioning tasks along this state machine and deciding, on `FAILED`, whether the failure is retryable (→ `RECOVERED`, requeued per its retry policy) or not (→ `TERMINATED`, surfaced to the caller) — this was previously attributed to "the Kernel" generally; it is specifically the Scheduler's decision.

---

## 9. Event flow (composite view)

```
External Request (API/CLI)
        │
        ▼
   Kernel.dispatch()  ──publishes──▶  task.created (event)
        │
        ▼
   dispatch("memory.retrieve_context@v1")  [sync, capability-resolved]
        │
        ▼
   dispatch("planning.decompose_task@v1")  [sync, capability-resolved]  ──publishes──▶ task.planned
        │
        ▼
   Kernel transitions task: QUEUED → EXECUTING   (admission decision made by Kernel Scheduler, §3b —
   respects priority, concurrency limits, and queue order before this transition happens)
        │
        ▼
   dispatch("agent.execute@v1") → dispatch("execution.run_step@v1")  [sync, per-step,
   capability-resolved — may be served by any registered agent/provider]  ──publishes──▶ task.step.completed
        │
        ▼
   dispatch("quality.validate_output@v1")  [sync, capability-resolved]
        │
        ├─ pass ──▶ Kernel transitions task: COMPLETED ──publishes──▶ task.completed
        └─ fail ──▶ Kernel transitions task: FAILED ──▶ recovery decision (§8)
        │
        ▼
   Response returned to caller (API/CLI)
```

Every `dispatch(...)` call above is resolved through the Capability Registry (§3a) at call time — the diagram intentionally never names a concrete service, because the Kernel doesn't either.

All `task.*` events are also consumed asynchronously by: the audit/event log (durable store), any subscribed plugins (via the Plugin Interface's event subscription capability), and observability/logging.

---

## 10. Explicitly out of scope for this proposal

- No source code, class definitions, or function signatures — architecture only, per your instruction.
- Plugin Interface wire format details (JSON schema, transport choice among stdio/HTTP/gRPC) — belongs in a Plugin Interface spec, Phase 3/4.
- Multi-model orchestration and AI provider adapter details — `GEN-0034`/`GEN-0035`/`GEN-0036`, unaffected by this proposal.
- This proposal does not touch or reopen the sealed-core-vs-self-evolution conflict (`Conflict_Report.md` §1) — the Kernel as specified here is static/immutable at runtime, consistent with the sealed-core decision already made.
