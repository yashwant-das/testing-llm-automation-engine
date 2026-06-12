# AI Engineering Workbench

> A reference implementation of AI Systems Engineering for Playwright test automation.
> Structured outputs · AST repair · evaluation · observability · explainability · local LLM.

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9%2B-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Playwright](https://img.shields.io/badge/Playwright-1.57%2B-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/)
[![Gradio](https://img.shields.io/badge/Gradio-6.2%2B-FF6B6B)](https://gradio.app/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Why This Exists

Writing and maintaining Playwright tests by hand is expensive. As UIs evolve, tests break — not because the product is broken, but because selectors drift, timeouts expire, or imports change. Fixing these failures manually is mechanical work that an AI system can do instead.

This project solves three problems:

1. **Test generation**: Given a URL and a plain-English scenario, produce a runnable Playwright spec.
2. **Visual generation**: Given a screenshot and an instruction, produce a test using only what is visible on screen.
3. **Self-healing**: When a spec breaks, diagnose why, propose a code fix, apply it, re-run the test, and repeat — bounded by a configurable retry limit.

The secondary goal is equally important: **demonstrate how to build reliable AI pipelines.** The system uses structured outputs (Pydantic), an evaluation framework (benchmarks), a custom observability layer (JSONL traces), AST-based code repair (ts-morph), and full provenance on every decision artifact. These are the engineering primitives any LLM application needs to be trustworthy in production.

---

## Core Capabilities

| Capability | Implementation |
| --- | --- |
| Test generation from DOM + accessibility tree | `src/services/generation_service.py` → `src/agents/generator.py` |
| Test generation from screenshot | `src/services/vision_service.py` |
| Self-healing pipeline | `src/services/healing_service.py` → `src/healing/` |
| Structured LLM outputs | `schemas/` + `src/utils/llm.parse_llm_response()` |
| AST-based code repair | `src/healing/repair.py` + `scripts/ast_repair.js` (ts-morph) |
| Heuristic failure classification | `src/healing/classifier.py` |
| Rich context collection | `src/context/` (DOM, accessibility tree, console errors, network errors, locator candidates) |
| LLM routing with retry and fallback | `src/llm/router.py` |
| JSONL observability traces | `src/observability/` |
| Evaluation benchmarks | `benchmarks/` |
| Full decision provenance | `HealingDecision.to_markdown()` (Phase 9 explainability fields) |

---

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                   Gradio UI (src/app.py)                    │
│  Overview │ Generation │ Healing │ Vision │ Artifacts │     │
│  Evaluation │ Traces │ Models                               │
└──────────────────────────────┬──────────────────────────────┘
                               │ calls only src/services/
┌──────────────────────────────▼──────────────────────────────┐
│                      src/services/                          │
│  generation_service  healing_service  workbench_service     │
│                   (streaming generators)                    │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                      Pipeline Layer                         │
│  src/healing/   src/context/                                │
│  src/agents/    src/observability/                          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │     src/llm/        │  LLMRouter → LM Studio / Ollama
                    │     schemas/        │  Pydantic validation
                    └─────────────────────┘
```

The UI layer calls only `src/services/`. Services call pipeline modules. Pipeline modules call `src/llm/` for LLM access and `schemas/` for data contracts. Every LLM call is recorded in `logs/traces.jsonl`. Every healing session produces a `HealingDecision` artifact in `tests/artifacts/`.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for Playwright and ts-morph AST repair)
- A running local LLM via [LM Studio](https://lmstudio.ai/) or [Ollama](https://ollama.com/)

### Install

```bash
# Python dependencies
uv sync

# Node.js dependencies + Playwright browsers
npm install
npx playwright install
```

### Configure LLM

Create a `.env` file:

```env
# For LM Studio (default)
LLM_PROVIDER=lm_studio
LM_STUDIO_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=your-model-name
LM_STUDIO_VISION_MODEL=your-vision-model-name

# For Ollama
LLM_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen3-coder:30b
```

### Run

```bash
uv run python src/app.py
```

Open `http://127.0.0.1:7860`.

---

## The Workbench

The UI has eight tabs:

### Overview

Shows the system status summary and a unified run history table — one row per decision artifact across all three pipelines (generation, healing, vision). Click **Refresh Recent Runs** to reload.

### Generation Pipeline

Enter a target URL and a plain-English test scenario. Click **Generate Test** to produce a TypeScript spec using the page's DOM structure, accessibility tree, and console signals. Click **Run Test** to execute it immediately.

### Healing Pipeline

Upload a broken `.spec.ts` file. Set **Max Repair Attempts** (1–5). Click **Run Healing Pipeline**. The pipeline:

1. Runs the test — captures the failure
2. Gathers evidence (error log, DOM, accessibility tree, console errors, network errors, screenshot)
3. Heuristic classifier pre-diagnoses the failure type (fast, deterministic, no LLM)
4. LLM plans the repair — reasons step-by-step, proposes a code fix
5. AST-based repair applies the fix (structural strategies: selector replace, import add, timeout adjust, role argument, assertion swap)
6. Verifies by re-running the test
7. Repeats up to the configured limit

The **Decision Report** tab shows the full `HealingDecision.to_markdown()` output — failure type, hypothesis, confidence score, confidence rationale, root cause evidence, code change, and provenance (model, prompt version, execution time).

### Vision Pipeline

Enter a URL and instruction. The pipeline captures a screenshot, sends it to a vision-capable LLM, and generates a test using visual signals. Useful when the DOM alone is not enough.

### Artifact Inspector

Browse `tests/artifacts/healing_decision_*.json` artifacts written after every healing session. Selecting an artifact renders the full markdown report alongside the raw JSON. The report includes Phase 9 provenance fields: which model, which prompt version and hash, how long the planning took, and which evidence snapshot was used.

### Evaluation

Two sub-tabs:

- **Heuristic Classification** — runs the heuristic failure-classification benchmark against `benchmarks/healing/fixtures/repair_scenarios.json`. No LLM or browser required, completes in milliseconds. Shows pass/fail per case with expected vs. classified failure type and confidence scores.
- **Generation (LLM)** — runs the generation benchmark against `benchmarks/generation/fixtures/web_scenarios.json`. Requires a live LLM.

### Trace Inspector

Load and inspect `logs/traces.jsonl`. Displays three tables — session spans, LLM call spans, and subprocess spans — all linked by `trace_id`. Useful for understanding token usage, latency distribution, and retry patterns without leaving the UI.

### Models

Displays active model configuration from environment variables (`LM_STUDIO_MODEL`, `LM_STUDIO_VISION_MODEL`, `OLLAMA_MODEL`, `OLLAMA_VISION_MODEL`) alongside capability metadata from the `ModelRegistry`. Click **Refresh** to reload.

---

## Running the Healing Pipeline Programmatically

```bash
# Via the service layer (correct entry point)
uv run python -c "
from src.services.healing_service import heal_test_streaming
for step in heal_test_streaming('tests/generated/broken_example.spec.ts', 3):
    print(step[0])
"
```

---

## Repository Structure

```text
.
├── src/
│   ├── app.py                    # Gradio UI — 8-tab workbench, wiring only
│   ├── agents/                   # Pipeline entry points
│   │   ├── generator.py          # Context collection + LLM → GenerationDecision
│   │   └── healer.py             # CLI entrypoint + re-exports src/healing/ public API
│   ├── services/                 # Service layer (UI → pipelines boundary)
│   │   ├── generation_service.py
│   │   ├── healing_service.py
│   │   ├── vision_service.py
│   │   └── workbench_service.py  # Overview, Artifact Inspector, Evaluation, Trace Inspector, Models
│   ├── healing/                  # Healing pipeline — 7 single-responsibility modules
│   │   ├── classifier.py         # Heuristic failure classification
│   │   ├── planner.py            # LLM reasoning → HealingDecision
│   │   ├── repair.py             # AST-first code repair
│   │   ├── runner.py             # Playwright subprocess management
│   │   ├── evidence.py           # Evidence gathering
│   │   ├── verifier.py           # Post-repair verification
│   │   └── artifact_store.py     # JSON artifact persistence
│   ├── context/                  # Rich browser context collection
│   │   ├── collector.py          # Unified ContextSnapshot builder
│   │   ├── dom.py                # HTML (BeautifulSoup-cleaned)
│   │   ├── accessibility.py      # Playwright accessibility tree → ARIA text
│   │   ├── locator_candidates.py # getByRole() strings from a11y tree
│   │   ├── console.py            # Browser console errors
│   │   ├── network.py            # Failed network requests
│   │   └── screenshot.py         # Screenshot capture
│   ├── llm/                      # LLM routing layer
│   │   ├── router.py             # LLMRouter with retry and fallback
│   │   ├── client.py             # LLMClientFactory (no module-level side effects)
│   │   ├── registry.py           # Model capability metadata
│   │   └── policies.py           # RetryPolicy, TimeoutPolicy
│   ├── observability/            # JSONL trace writer
│   │   ├── tracer.py             # Tracer (thread-local sessions) + NullTracer
│   │   ├── writer.py             # Thread-safe JSONL appender
│   │   └── schemas.py            # SubprocessSpan, SessionSpan, TraceSession
│   └── utils/
│       ├── llm.py                # parse_llm_response() + extract_json_block(), extract_code_block()
│       ├── prompt_loader.py      # load_prompt(), get_prompt_hash(), get_prompt_version()
│       ├── browser.py            # extract_domain() — URL → clean domain name for filenames
│       ├── formatting.py         # clean_ansi_codes(), format_test_result()
│       └── validation.py         # Input validation
├── schemas/                      # Pydantic data contracts
│   ├── healing.py                # HealingAnalysis, HealingDecision, Evidence, HealingAction
│   ├── generation.py             # GenerationResult, GenerationDecision, VisionDecision
│   ├── evaluation.py             # BenchmarkRun, BenchmarkRunConfig, EvaluationResult
│   ├── artifacts.py              # ContextSnapshot, TraceMetadata
│   └── shared.py                 # FailureType, RunResult, ProvenanceRecord, LLMConfig
├── benchmarks/                   # Evaluation framework
│   ├── healing/
│   │   ├── runner.py             # Healing benchmark runner
│   │   └── fixtures/
│   │       └── repair_scenarios.json
│   ├── generation/
│   │   ├── runner.py
│   │   └── fixtures/
│   │       └── web_scenarios.json
│   ├── intent_validation/
│   │   └── runner.py
│   └── mutations/
│       └── mutator.py            # Mutation engine (introduces known failure types)
├── scripts/
│   └── ast_repair.js             # ts-morph AST repair script (Node.js subprocess)
├── prompts/                      # LLM system prompts (external markdown files)
│   ├── generator.md
│   ├── healer.md
│   ├── vision.md
│   └── manifest.json             # Version registry (human-set version + dynamic hash)
├── docs/                         # Project documentation
│   ├── architecture/             # Per-subsystem architecture documents
│   ├── evaluation/               # Benchmark and evaluation documentation
│   ├── prompts/                  # Prompt design and versioning documentation
│   ├── development/              # Developer onboarding and contribution guides
│   ├── history/                  # Archived planning and evaluation documents
│   ├── decisions.md              # Architecture Decision Records
│   ├── scorecard.md              # Repository maturity scorecard
│   ├── backlog.md                # Future work and research topics
│   ├── governance.md             # Documentation governance rules
│   ├── docker.md                 # Docker setup and deployment
│   └── env-variables.md          # Environment variable reference
├── tests/
│   ├── unit_test_*.py            # 553 unit tests (zero live LLM or browser calls)
│   ├── fixtures/                 # Broken .spec.ts files for benchmark/repair testing
│   ├── generated/                # Generated specs (runtime output)
│   └── artifacts/                # HealingDecision JSON artifacts (runtime output)
├── logs/
│   └── traces.jsonl              # JSONL observability traces (runtime output)
├── playwright.config.ts
├── pyproject.toml
└── package.json
```

---

## Evaluation System

The `benchmarks/` directory contains a reproducible evaluation framework with three runners:

**Healing benchmark** (`benchmarks/healing/runner.py`):

- Classification-only mode: runs `classify_failure_heuristic()` against synthetic error logs. No LLM needed. Deterministic.
- Full repair mode: optionally calls a `healer_fn(code, error_log)` and evaluates the repaired code against lexical checks.
- Dataset: `benchmarks/healing/fixtures/repair_scenarios.json` — 4 cases covering LOCATOR_NOT_FOUND, TIMEOUT, JAVASCRIPT_ERROR, ASSERTION_FAILED.

**Generation benchmark** (`benchmarks/generation/runner.py`):

- Evaluates generated code quality with lexical checks (imports, assertions, selector preferences).
- Requires a live LLM but no browser.

**Intent validation** (`benchmarks/intent_validation/runner.py`):

- Checks that generated tests encode the original user intent (6 lexical assertions).

Every benchmark run records: model, prompt version, prompt hash, temperature, seed, dataset version, and timestamp. Results are exportable to JSON for cross-run comparison.

```bash
# Run the classification benchmark from Python
uv run python -c "
from benchmarks.healing.runner import load_dataset, run_healing_benchmark
from schemas.evaluation import BenchmarkRunConfig
from pathlib import Path

config = BenchmarkRunConfig(
    model='heuristic-classifier', provider='local',
    prompt_name='classify_failure_heuristic', prompt_version='1', prompt_hash='n/a',
    temperature=0.0, dataset_version='1.0.0', benchmark_type='healing-classification',
)
run = run_healing_benchmark(
    Path('benchmarks/healing/fixtures/repair_scenarios.json'),
    Path('.'), config,
)
print(f'{run.passed}/{run.total} passed ({run.pass_rate*100:.0f}%)')
"
```

---

## Observability

Every healing session writes spans to `logs/traces.jsonl`:

```jsonl
{"span_type":"llm","trace_id":"a1b2...","model":"qwen3-coder-30b","input_tokens":4821,"output_tokens":312,"latency_ms":3400,"retry_count":0}
{"span_type":"subprocess","trace_id":"a1b2...","command":"npx playwright test ...","exit_code":0,"latency_ms":7100}
{"span_type":"session","trace_id":"a1b2...","session_type":"healing","llm_call_count":1,"total_input_tokens":4821,"total_latency_ms":12600,"success":true}
```

Query with `jq`:

```bash
# Token usage per session
jq 'select(.span_type=="session") | {trace_id, total_input_tokens, total_output_tokens, success}' logs/traces.jsonl

# LLM calls with retries
jq 'select(.span_type=="llm" and .retry_count > 0)' logs/traces.jsonl

# Slowest Playwright runs
jq 'select(.span_type=="subprocess") | {command, latency_ms}' logs/traces.jsonl | sort
```

The Trace Inspector tab in the workbench renders these tables without needing `jq`.

---

## Technology Choices

| Decision | Choice | Why |
| --- | --- | --- |
| Schema validation | Pydantic v2 | Runtime validation, JSON schema export, field coercion, IDE completions. See ADR-001. |
| LLM client | OpenAI SDK (thin wrapper) | Both LM Studio and Ollama expose OpenAI-compatible APIs. LiteLLM adds 40 MB for no benefit here. See ADR-007. |
| TypeScript AST repair | ts-morph (Node.js subprocess) | TypeScript-native, read/write AST, formatting-preserving. Babel strips types; tree-sitter is read-only. See ADR-003. |
| Observability | Custom JSONL tracer | Zero new dependencies. LLMRouter already captures all required signals. `jq` satisfies all query needs. See ADR-004. |
| Prompt storage | External markdown files + `manifest.json` | Diffable, human-editable, independently versioned. See ADR-005. |
| UI framework | Gradio | Streaming generators map directly to Gradio's `yield`-based progress model. |
| UI-to-pipeline boundary | Service layer | `app.py` imports only from `src/services/`. Services import from pipeline modules. See ADR-006. |
| Browser context | Single Playwright session | Context collector opens one browser, collects DOM + a11y tree + console + network + screenshot, closes. |

---

## Development Commands

```bash
# Run all unit tests (553 tests, no live LLM or browser required)
uv run python -m pytest tests/unit_test_*.py -q

# Lint and format (Python + TypeScript + Markdown)
npm run lint
npm run format

# Run the Playwright smoke suite
npm run test

# Run a specific unit test file
uv run python -m pytest tests/unit_test_healing.py -v
```

---

## Further Reading

- [`docs/architecture/overview.md`](docs/architecture/overview.md) — system architecture with component map
- [`docs/architecture/healing.md`](docs/architecture/healing.md) — healing pipeline deep dive with sequence diagram
- [`docs/ai-systems-engineering.md`](docs/ai-systems-engineering.md) — AI engineering patterns used in this project
- [`docs/development/setup.md`](docs/development/setup.md) — full setup and troubleshooting guide
- [`docs/development/adding-models.md`](docs/development/adding-models.md) — how to add a new LLM provider
- [`docs/decisions.md`](docs/decisions.md) — all Architecture Decision Records
- [`docs/history/`](docs/history/) — phase-by-phase completion records and archived plans
