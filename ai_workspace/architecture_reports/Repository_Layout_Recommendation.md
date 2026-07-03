# Repository Layout Recommendation — GENESIS OS

**Conflict being resolved:** `README.md`'s top-level repo structure (`docs/ src/ plugins/ tests/ config/ logs/ scripts/`) vs. `CODING_STANDARDS.md`'s `src/` internal structure, which lists `plugins/`, `config/`, and `tests/` *nested inside* `src/`. Phase 1 resolved this pragmatically without a documented decision; this document makes it official.

## Recommendation: **Option A — `src/` layout**, with one adjustment

```
GENESIS_OS/
├── src/
│   ├── core/           # sealed kernel (KERNEL_ARCHITECTURE_PROPOSAL.md)
│   ├── runtime/         # execution engine, state machine, orchestration
│   ├── plugins/         # Plugin Manager: loader, registry, isolation (CODE, not plugin packages)
│   ├── plugin_sdk/       # base classes for first-party Python plugins
│   ├── api/              # FastAPI layer
│   ├── cli/              # Typer CLI
│   ├── config/           # settings-loading code (reads env/.env)
│   ├── database/         # SQLAlchemy models + Alembic migrations
│   ├── services/         # Memory, vector search (Qdrant), cache (Redis)
│   └── utils/
├── tests/
│   ├── unit/
│   └── integration/
├── plugins/               # INSTALLED plugin packages (data, not source) — any language
├── config/                 # runtime config FILES (yaml/json/env templates) — not code
├── docs/                    # sealed architecture spec (GEN-0000-0203)
├── ai_workspace/
├── logs/
├── scripts/
└── pyproject.toml / requirements.txt
```

**The adjustment:** the naming collision between `src/plugins/` and top-level `plugins/` (same for `config/`) is kept, but their meaning is fixed and documented: `src/X` is always *code*, top-level `X` is always *data/artifacts*. This is what Phase 1 already implemented; this document formalizes it rather than changing it.

## Why Option A, not Option B

**Option B** (`core/`, `runtime/`, `plugins/` directly at repo root, no `src/`) is what a literal reading of `README.md`'s top-level list plus `CODING_STANDARDS.md`'s package names combined would look like if you drop the `src/` wrapper. It was seriously considered and rejected for three reasons:

1. **Import ambiguity.** Without a `src/` root, `core`, `runtime`, etc. become top-level importable packages sitting next to non-code directories (`docs/`, `logs/`, `assets/`) in the same namespace as the project root. This makes it easy to accidentally shadow a stdlib or third-party package name (`config`, `services`, and `utils` are common third-party package names too), and makes `pip install -e .` / packaging metadata (`pyproject.toml`'s `[tool.setuptools.packages.find]`, already configured in Phase 1) messier to get right. `src/` layout is the current Python Packaging Authority-recommended default specifically to avoid this class of bug — it forces the package to be installed rather than accidentally importable from the working directory during tests, which catches "works on my machine because of CWD" bugs before they ship.
2. **Directly reflects the sealed-core rule.** `GEN-0002_Core_Principles.md` and `README.md` are explicit that "the Core Architecture is complete and immutable" and "must never be modified by implementation code." Having a single `src/` root makes the code/non-code boundary a directory boundary (`src/` = implementation, everything else = spec, data, or docs) — which is a useful, visible enforcement aid for a rule the project already cares about. Option B blurs this because `core/` would sit at the same tree level as `docs/`, making "is this a spec document or an implementation module" a per-directory judgment call instead of a structural one.
3. **Consistency with the already-shipped Phase 1 skeleton.** Phase 1 already built `src/`-layout (with `__init__.py` docstrings referencing the architecture docs). Choosing Option B now would mean redoing completed work for a naming preference with no functional advantage — `CODING_STANDARDS.md`'s literal text technically supports Option A already (its "Project Structure" section shows exactly this `src/core/ src/runtime/ ...` tree), so Option A is also the reading more faithful to that document, not just the path of least churn.

**Where README.md's top-level list still applies:** `docs/`, `tests/`, `config/`, `plugins/`, `logs/`, `scripts/` remain top-level as README specifies — they're artifact/data directories, not Python packages, so they were never actually in conflict with `src/`-layout in the first place. The only real conflict was `CODING_STANDARDS.md` nesting `tests/`/`plugins/`/`config/` *inside* `src/`, which this document rejects in favor of the code/data split above.

## Decision record

| Question | Answer |
|---|---|
| `src/` wrapper for Python code? | Yes |
| `tests/` location | Top-level (pytest convention; not Python package code) |
| `plugins/` (installed packages) location | Top-level `plugins/` (data) |
| `plugins/` (loader code) location | `src/plugins/` (code) |
| `config/` (files) location | Top-level `config/` (data) |
| `config/` (settings-loading code) location | `src/config/` (code) |

This is a documentation change only — no directories move. Phase 1's skeleton already matches this recommendation.
