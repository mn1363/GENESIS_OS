# BUILD_INSTRUCTION.md

## GENESIS OS — Master Build Instructions

### Project Mission

You are implementing a real production-quality software system from the architectural specification contained in the `/docs` directory.

The documents describe the intended architecture. They are not implementation code.

Your responsibility is to transform the specification into a working software platform while preserving the architecture.

---

# Primary Objective

Build a complete, modular, extensible, production-ready implementation of GENESIS OS.

Do not rewrite the documentation.

Implement it.

---

# General Rules

1. Read every document in `/docs` before writing implementation code.

2. Build a dependency graph between documents.

3. Detect architectural relationships.

4. Never ignore newer architectural decisions.

5. If two documents conflict, prefer the latest version and report the conflict.

6. Never invent a different architecture when the specification already defines one.

7. Produce production-quality code.

8. Every module must be independently testable.

9. Prefer composition over inheritance.

10. Use dependency injection where appropriate.

11. Keep modules loosely coupled.

12. Maintain deterministic behavior whenever practical.

---

# Development Process

Phase 1

* Analyze documentation
* Extract architecture
* Build dependency map

Phase 2

* Create repository structure

Phase 3

* Implement Runtime Core

Phase 4

* Implement Plugin Manager

Phase 5

* Implement Plugin SDK

Phase 6

* Implement Execution Engine

Phase 7

* Implement Official Plugins

Phase 8

* Implement REST API

Phase 9

* Implement CLI

Phase 10

* Implement Desktop/Web UI

Phase 11

* Testing

Phase 12

* Packaging

---

# Coding Requirements

* Python 3.13
* FastAPI
* AsyncIO
* SQLAlchemy
* Pydantic
* Typer CLI
* Pytest

---

# Architecture Preservation

The GENESIS OS Core Architecture is immutable.

Implementation must not modify architectural intent.

The runtime extends capability without altering the sealed core.

---

# Plugin Requirements

Plugins must:

* be isolated
* be versioned
* declare dependencies
* expose a standard interface
* run inside controlled execution environments

---

# Security

* Validate all external input.
* Never execute untrusted code directly.
* Isolate plugins.
* Enforce permission checks.
* Log critical events.

---

# Error Handling

Every subsystem must:

* detect failures
* isolate failures
* recover safely where possible
* produce structured logs

---

# Deliverables

For every completed phase provide:

* Source code
* Tests
* Documentation
* Example usage
* Known limitations

Do not skip phases.

Do not leave placeholder implementations.

The final result must be executable.
