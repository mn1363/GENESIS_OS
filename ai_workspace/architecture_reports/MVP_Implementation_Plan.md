# MVP Implementation Plan — GENESIS OS

This plan draws **only** from documents classified "Implementable Architecture" or "Supporting Architecture" in `Document_Classification.md`. No "Conceptual/Vision," "Deprecated/Duplicate," or "Conflicting" document is referenced here. No code is included — this is Phase 0 scope planning only, per the MASTER_PROMPT constraint.

## 1. Recommended MVP boundary

The 48 Implementable documents describe a 5-stage agent pipeline plus a shared memory store. This matches the MVP scope already agreed on in prior sessions:

```
User Goal → Planner → Agent Executor → Quality Check → Task Complete
                              ↕
                        Memory Store
```

Mapped to source documents:

| MVP component | Primary source docs |
|---|---|
| User Goal intake | GEN-0000 Project Manifest, GEN-0001 Project Vision |
| Planner | GEN-0006 Planner Architecture, GEN-0032 Task Decomposition Engine, GEN-0033 Execution Planner |
| Agent Executor | GEN-0007 Agent Architecture, GEN-0024 Agent Runtime, GEN-0023 Workflow Runtime, GEN-0008 Execution Engine, `Runtime_Task_Execution_Protocol_v1`, `Runtime_Task_Orchestration_Engine_v1` |
| Quality Check | GEN-0009 Quality Engine, GEN-0037 Quality Assurance Framework |
| Task Complete | `Runtime_Full_Execution_Trace_Reference_Case_v1` (defines what a completed task record looks like) |
| Memory Store | GEN-0005 Memory Architecture, GEN-0022 Data Model, GEN-0021 Storage Architecture, GEN-0026 Vector Memory Architecture |
| Bootstrap/CLI shell | `Runtime_Bootstrap_Application_Layer_v1`, `Runtime_Execution_State_Machine_v1`, GEN-0017 Configuration System |

This is deliberately a small slice: 15 of the 48 Implementable documents. The remaining 33 Implementable docs (Plugin Architecture, Knowledge Graph, Prompt/Template system, AI Provider Abstraction, Multi-Model Orchestration, Testing/Release/Deployment, project-tracking spine) are real and usable but not required for a first working loop.

## 2. Phased plan

**Phase 1 — Core loop (the 15 docs above).** Single agent, single task, no plugins, no multi-model routing. Goal: prove the Planner → Executor → Quality → Complete loop runs end to end with a real Memory Store, matching the already-scoped MVP.

**Phase 2 — Extend the agent layer.** Add GEN-0029 Agent Catalog, GEN-0030 Agent Communication Protocol, GEN-0034 AI Provider Abstraction Layer, GEN-0035 Model Capability Framework, GEN-0036 Multi-Model Orchestration — enables multiple agents/models instead of one.

**Phase 3 — Add extensibility.** GEN-0015 Event System, GEN-0016 Plugin Architecture, `Runtime_Plugin_Interface_Standard_v1` — enables third-party tools/plugins without touching the core loop.

**Phase 4 — Add project-tracking spine.** GEN-0011 Project Memory Model, GEN-0012 Decision Log System, GEN-0013 Project Workflow, GEN-0014 Project State Model — needed once tasks span multiple sessions.

**Phase 5 — Production hardening (Supporting Architecture, as needed).** Pull individual documents from the 40-doc Supporting set only when the corresponding need actually arises: GEN-0067 Secrets Management before handling real credentials, GEN-0042 Observability before running unattended, GEN-0047 Compliance/GEN-0048 Data Governance only if handling regulated data, GEN-0069 Cost Management once using paid model APIs at volume. Do not front-load all 40 — most MVPs never need Service Mesh (GEN-0060) or Disaster Recovery (GEN-0065) architecture on day one.

## 3. Explicitly out of scope

- All 85 Conceptual/Vision documents (`GEN-0100+` and scattered earlier entries) — no implementable mechanism, see `Document_Classification.md`.
- All 14 Conflicting documents — either contradict the sealed-core rule or make a false "final closure" claim; see `Conflict_Report.md`.
- All 26 Deprecated/Duplicate documents — redundant with a document already in this plan.

## 4. Immediate blockers to resolve before Phase 1 coding starts — RESOLVED

1. Write or fold in a real Kernel Architecture (GEN-0004 is empty/corrupted — see `Conflict_Report.md` §3). **Still open** — will be addressed by folding kernel responsibilities into `src/core/` during Phase 2 (Runtime Core), per `PROJECT_ROADMAP.md`.
2. Record the sealed-core decision explicitly (`Conflict_Report.md` §1) so it isn't revisited mid-build. **Resolved** — sealed-core principle stands; the four self-evolution documents remain out of scope.
3. Confirm the technology stack. **Resolved by architecture decision (2026-07-02):**

| Layer | Choice |
|---|---|
| Core runtime language | Python 3.13 |
| Core framework | FastAPI |
| CLI | Typer |
| Database (dev) | SQLite |
| Database (prod) | PostgreSQL |
| Vector memory | Qdrant |
| Cache | Redis |

**Polyglot plugin rule:** the Core Runtime is Python-only; plugins may be written in any language provided they communicate exclusively through the official Plugin Interface and Runtime API. The Core must never import or directly depend on a plugin's implementation language or runtime. This means the Plugin Interface (`Runtime_Plugin_Interface_Standard_v1`) is a **process/IPC boundary**, not an in-process Python interface — plugin communication should be assumed to go over a serialized protocol (e.g. JSON over stdio/HTTP/gRPC), not a Python function call, so that a plugin written in another language is structurally no different from one written in Python.

This supersedes the earlier Node.js CLI framing from prior sessions — the CLI is Typer (Python), not Node.js. The distributed/Raft-based ATLAS trading engine work remains a separate Node.js project, unaffected by this decision.

