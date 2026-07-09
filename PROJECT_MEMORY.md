# GENESIS OS - Project Memory

## Architecture Decisions

The project follows strict Clean Architecture.

Core rules:

- Kernel never depends on Runtime.
- Runtime never depends on Storage implementations.
- All services are resolved through Dependency Injection.
- Repository Pattern is mandatory.
- Atomic patches only.
- Production quality only.
- No placeholder implementations.
- No breaking API.

---

## Completed Integrations

Knowledge Graph

Production SQLAlchemy backend integrated.

Memory

Knowledge Graph wired through DI.

Redis Short-Term Memory wired through DI.

Qdrant Vector Memory wired through DI.

---

## Testing Status

Current tests:

228 passed

Coverage:

96%

Static analysis:

Ruff PASS

mypy PASS

---

## Current Development Strategy

Each milestone must follow:

Claude
↓

Atomic Patch

↓

Project Manager Review

↓

git am

↓

ruff

↓

mypy

↓

pytest

↓

git push

↓

Milestone Closed

No patch is merged without architectural review.