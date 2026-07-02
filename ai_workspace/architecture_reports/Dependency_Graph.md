# Architecture Dependency Graph — GENESIS OS

Scope: only "Implementable Architecture" and "Supporting Architecture" documents (88 of 213) have real dependency edges — a document with no interface or data model has nothing for another document to depend on, so "Conceptual / Vision" documents are excluded here (they're structurally disconnected: arrows in those docs point to other invented layers, not to anything defined elsewhere in the corpus).

## 1. Core execution spine (Implementable, GEN-0000–0041)

```
GEN-0000 Project Manifest
  └─ GEN-0001 Project Vision
       └─ GEN-0002 Core Principles
            └─ GEN-0003 System Architecture
                 ├─ GEN-0005 Memory Architecture  (see Conflict_Report.md — GEN-0004 slot is empty/corrupted)
                 ├─ GEN-0006 Planner Architecture
                 ├─ GEN-0007 Agent Architecture
                 ├─ GEN-0008 Execution Engine
                 ├─ GEN-0009 Quality Engine
                 └─ GEN-0010 Context Engine

GEN-0006 Planner Architecture
  └─ GEN-0032 Task Decomposition Engine
       └─ GEN-0033 Execution Planner
            └─ GEN-0008 Execution Engine
                 └─ GEN-0023 Workflow Runtime
                      └─ GEN-0024 Agent Runtime
                           ├─ GEN-0007 Agent Architecture
                           ├─ GEN-0029 Agent Catalog
                           └─ GEN-0030 Agent Communication Protocol

GEN-0010 Context Engine
  └─ GEN-0031 Context Assembly Engine
       ├─ GEN-0005 Memory Architecture
       ├─ GEN-0025 Knowledge Graph Architecture
       └─ GEN-0026 Vector Memory Architecture

GEN-0009 Quality Engine
  └─ GEN-0037 Quality Assurance Framework
       ├─ GEN-0038 Testing Architecture
       └─ GEN-0039 Code Review Framework
            └─ GEN-0040 Release Management Framework
                 └─ GEN-0041 Deployment Architecture

GEN-0027 Prompt Architecture
  └─ GEN-0028 Template System
       └─ GEN-0034 AI Provider Abstraction Layer
            ├─ GEN-0035 Model Capability Framework
            └─ GEN-0036 Multi-Model Orchestration

GEN-0016 Plugin Architecture
  └─ GEN-0015 Event System
       └─ GEN-0017 Configuration System
            └─ GEN-0018 Logging and Observability

GEN-0020 API Gateway Architecture
  └─ GEN-0021 Storage Architecture
       └─ GEN-0022 Data Model

GEN-0011 Project Memory Model → GEN-0012 Decision Log System → GEN-0013 Project Workflow → GEN-0014 Project State Model
  (project-tracking spine — orthogonal to the agent execution spine above; both read/write GEN-0022 Data Model)
```

## 2. Runtime layer (Implementable, `GENESIS_OS_Runtime_*_v1.md`)

These sit **on top of** the core spine and are the closest thing in the corpus to an actual build order:

```
GENESIS_OS_Runtime_Bootstrap_Application_Layer_v1
  └─ GENESIS_OS_Runtime_Execution_State_Machine_v1
       └─ GENESIS_OS_Runtime_Task_Orchestration_Engine_v1
            └─ GENESIS_OS_Runtime_Task_Execution_Protocol_v1
                 ├─ GENESIS_OS_Runtime_Plugin_Interface_Standard_v1  (implements GEN-0016 Plugin Architecture)
                 └─ GENESIS_OS_Runtime_System_API_Gateway_v1        (implements GEN-0020 API Gateway Architecture)
                      └─ GENESIS_OS_Runtime_Full_Execution_Trace_Reference_Case_v1  (worked example / acceptance test)
```

## 3. Supporting layer (GEN-0042–0099, minus duplicates)

Attaches to the spine above as cross-cutting concerns rather than a separate pipeline:

```
GEN-0042 Observability Framework ──┐
GEN-0043 Incident Response ────────┼── attach to GEN-0023 Workflow Runtime / GEN-0024 Agent Runtime
GEN-0045 Identity & Access Mgmt ───┤
GEN-0046 Policy Engine ────────────┘

GEN-0047 Compliance Framework
  └─ GEN-0048 Data Governance Architecture
       └─ GEN-0049 Data Lineage Framework
            (all three attach to GEN-0022 Data Model)

GEN-0062 Database Architecture ── GEN-0063 Caching ── GEN-0064 Backup & Recovery ── GEN-0065 Disaster Recovery
  (all attach to GEN-0021 Storage Architecture)

GEN-0067 Secrets Management ── GEN-0068 Resource Management ── GEN-0069 Cost Management ── GEN-0070 Provider Management
  (all attach to GEN-0034 AI Provider Abstraction Layer)

GEN-0076 Agent Collaboration ── GEN-0078 Agent Capability ── GEN-0079 Agent Lifecycle ── GEN-0080 Agent Orchestration
  (all attach to GEN-0024 Agent Runtime)
```

## 4. Structural observations

- **No cycles found** within the Implementable set — the spine is a clean DAG.
- **GEN-0004's absence is a real gap**, not just a naming issue: nothing downstream references "Kernel Architecture" content specifically, but `GEN-0003 System Architecture` assumes a kernel layer exists beneath Memory/Planner/Agent/Execution/Quality/Context. That assumption is currently undocumented.
- **The Supporting layer has no dependencies among Conceptual/Vision documents** — none of the `GEN-0100+` documents are referenced by anything in the Implementable or Supporting sets, and nothing in the Implementable/Supporting sets is referenced by them either. They are architecturally an island, not an extension of the core.
- **Duplicate documents (26 total) sit outside this graph** — each duplicate covers the same node as its earlier counterpart and adds no new edges; see `Document_Classification.md` for the full pairing.
