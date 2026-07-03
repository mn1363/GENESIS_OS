# Tests

- `unit/` — one test module per `src/` module, no external services required.
- `integration/` — exercises real SQLite/Qdrant/Redis (via docker-compose, added in Phase 2).

Run: `pytest` (config in `pyproject.toml`).
No tests exist yet — this is Phase 1 scaffolding. Test implementation begins alongside each component in its respective phase (per PROJECT_ROADMAP.md Phase 11 is dedicated hardening, but unit tests are written per-phase, not deferred).
