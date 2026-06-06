# Repository Guidelines

> Instructions for AI assistants (Claude, Codex, etc.) working in this codebase.
> Verified against the current codebase as of 2026-06-06.

---

## What This Project Is

A reference AI Systems Engineering project — not a SaaS product. It implements
Playwright test generation and self-healing using local LLMs with structured outputs,
evaluation, observability, and AST-based repair. The goal is a reference-quality
implementation of the patterns described in `docs/ai-systems-engineering.md`.

---

## Module Structure

```text
src/
├── app.py                # Gradio UI — 6-tab workbench, wiring only
├── agents/               # Compatibility shims (do not add new logic here)
│   ├── generator.py      # Delegates to src/context/ + src/llm/
│   ├── healer.py         # Thin shim → src/healing/ (targeted for removal)
│   └── vision.py         # Vision pipeline
├── services/             # Service layer — the boundary between UI and pipelines
│   ├── generation_service.py
│   ├── healing_service.py
│   ├── vision_service.py
│   └── workbench_service.py
├── healing/              # Healing pipeline — 7 single-responsibility modules
│   ├── classifier.py     # Heuristic failure classification (pure function)
│   ├── planner.py        # LLM reasoning → HealingDecision
│   ├── repair.py         # AST-first code repair + string fallback
│   ├── runner.py         # Playwright subprocess management
│   ├── evidence.py       # Evidence gathering
│   ├── verifier.py       # Post-repair verification
│   └── artifact_store.py # JSON artifact persistence
├── context/              # Browser context collection (single Playwright session)
│   ├── collector.py      # Unified ContextSnapshot builder
│   ├── dom.py, accessibility.py, locator_candidates.py
│   ├── console.py, network.py, screenshot.py
├── llm/                  # LLM routing layer
│   ├── router.py         # LLMRouter with retry and fallback
│   ├── client.py         # LLMClientFactory (no module-level side effects)
│   ├── registry.py       # Model capability metadata
│   └── policies.py       # RetryPolicy, TimeoutPolicy
├── observability/        # JSONL trace writer
│   ├── tracer.py         # Tracer (thread-local) + NullTracer
│   ├── writer.py         # Thread-safe JSONL appender
│   └── schemas.py        # Span models
└── utils/
    ├── llm.py            # parse_llm_response() — public API. Other functions deprecated.
    ├── prompt_loader.py  # load_prompt(), get_prompt_hash(), get_prompt_version()
    └── validation.py     # Input validation

schemas/                  # Pydantic data contracts (source of truth for all data shapes)
├── healing.py            # HealingAnalysis, HealingDecision, Evidence, HealingAction
├── generation.py         # GenerationResult
├── evaluation.py         # BenchmarkRun, BenchmarkRunConfig, EvaluationResult
├── artifacts.py          # ContextSnapshot, TraceMetadata
└── shared.py             # FailureType, RunResult

benchmarks/               # Evaluation framework
scripts/
└── ast_repair.js         # ts-morph AST repair script (Node.js subprocess)
prompts/                  # LLM system prompts (external markdown files)
```

---

## Where to Add New Code

| What you're adding | Where it goes |
| --- | --- |
| New LLM provider | `src/llm/client.py` + `src/llm/registry.py` (see `docs/development/adding-models.md`) |
| New repair strategy | `src/healing/repair.py` + `schemas/healing.py` + `scripts/ast_repair.js` (see `docs/development/adding-healing-strategies.md`) |
| New benchmark | `benchmarks/<type>/` + dataset JSON (see `docs/development/adding-benchmarks.md`) |
| New failure classification pattern | `src/healing/classifier.py` + `benchmarks/healing/fixtures/repair_scenarios.json` |
| New UI tab | `src/services/` first, then wire in `src/app.py` |
| New data contract | `schemas/` as a Pydantic `BaseModel` |
| New context collector | `src/context/` + register in `src/context/collector.py` |

**Do not add logic to `src/agents/`.** This package is a compatibility shim layer and is
targeted for removal. All new pipeline logic goes into `src/healing/`, `src/context/`,
`src/services/`, or `src/llm/`.

---

## Build, Test, and Development Commands

```bash
# Install Python dependencies
uv sync

# Install Node.js + Playwright browsers
npm install && npx playwright install

# Run all Python unit tests (no live LLM or browser required — 440 tests)
uv run python -m pytest tests/unit_test_*.py -q

# Run the classification benchmark (deterministic, no LLM)
uv run python -c "
from benchmarks.healing.runner import run_healing_benchmark
from schemas.evaluation import BenchmarkRunConfig
from pathlib import Path
config = BenchmarkRunConfig(
    model='heuristic', provider='local',
    prompt_name='n/a', prompt_version='1', prompt_hash='n/a',
    temperature=0.0, dataset_version='1.0.0', benchmark_type='healing-classification',
)
run = run_healing_benchmark(Path('benchmarks/healing/fixtures/repair_scenarios.json'), Path('.'), config)
print(f'{run.passed}/{run.total} passed')
"

# Lint (JS + Python + Markdown)
npm run lint

# Format Python
uv run ruff format .

# Launch the workbench (requires LLM for generation/healing tabs)
uv run python src/app.py
# Open http://127.0.0.1:7860

# Run Playwright E2E tests
npm run test
```

---

## Testing Guidelines

- All Python tests are in `tests/unit_test_*.py`. Use `unittest.TestCase`.
- Tests must NOT require a live LLM, live browser, or network connection.
- Mock the LLM router with `@patch("src.healing.planner.get_default_router")`.
- Mock the Playwright page with `MagicMock()` for context collector tests.
- The `model_used` attribute on mock `LLMResponse` objects must be a string (not a `MagicMock`).
- See `docs/development/testing.md` for full patterns.

---

## Coding Style

- Python: Ruff (88-char lines, double quotes). Run `uv run ruff format .` before committing.
- TypeScript: Prettier with 2-space indentation. Run `npm run format` before committing.
- Markdown: must pass `markdownlint-cli2`. Run `npm run lint:md` to check.
- All LLM responses must be parsed via `parse_llm_response(raw, ModelClass)` — never `json.loads()` directly.
- All new data contracts must be Pydantic `BaseModel` subclasses in `schemas/`.

---

## Commit Guidelines

- Use Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`.
- Include before/after artifacts when healing logic changes.
- Run `npm run lint` and `uv run python -m pytest tests/unit_test_*.py -q` before committing.

---

## Documentation

Active documentation lives in:

- `README.md` — entry point, architecture overview, quick start
- `docs/decisions.md` — all Architecture Decision Records (ADR-001 through ADR-011)
- `docs/architecture/` — per-subsystem architecture docs
- `docs/development/` — contributor guides
- `docs/evaluation/` — benchmark and evaluation methodology
- `docs/prompts/` — prompt engineering documentation

Historical documents (completed plans, pre-decision evaluations) are in `docs/history/`.

---

## Security

- Do not commit `.env` files or real API keys.
- All subprocess calls use list arguments — no shell injection risk.
- Prompt changes go in `prompts/`; increment the version in `prompts/manifest.json`.
