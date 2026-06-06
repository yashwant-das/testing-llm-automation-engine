# Modernization Plan

> Based on Phase 0 audit completed 2026-06-06.
> See `architecture-review.md` for full findings.
> Priority: foundations before features.

---

## Guiding Principles

1. Delete more than you add.
2. Simplify rather than abstract.
3. No new user-facing features until structured outputs, evaluation, and architecture cleanup are complete.
4. Every change must be measurable (scorecard, tests, or benchmarks).

---

## Phase 1 — Structured Outputs Foundation

**Priority:** Highest. Everything else depends on reliable LLM communication.

### Problem

All LLM responses are parsed with regex and brace-slicing. Schema is enforced manually. Any model output variation causes silent data corruption.

### Deliverables

```text
schemas/
├── __init__.py
├── generation.py      # GenerationRequest, GenerationResult
├── healing.py         # HealingRequest, HealingDecision (Pydantic)
├── evaluation.py      # BenchmarkRun, EvaluationResult
├── artifacts.py       # ArtifactRecord, ContextSnapshot
└── shared.py          # FailureType enum, RunResult, ProviderConfig
```

Replace `src/models/healing_model.py` dataclasses with Pydantic `BaseModel` subclasses in `schemas/`.

### Success Criteria

- Zero `extract_json_block()` calls remain in production paths
- Zero `extract_code_block()` calls remain without a structured fallback
- All LLM responses validated against a Pydantic schema before use
- Schema tests exist for all models
- Validation failures trigger retry, not silent corruption

### Estimated Effort: 3–5 days

---

## Phase 2 — LLM Layer Modernization

**Priority:** High. Blocks reliable local LLM use and provider flexibility.

### Problem

Single OpenAI client initialized at module level. No retry, no fallback, no model registry. Testability requires module patching.

### Deliverables

```text
src/llm/
├── __init__.py
├── client.py          # LLMClientFactory; no module-level side effects
├── registry.py        # Model registry with capability metadata
├── router.py          # LiteLLM-based routing with fallback chains
└── policies.py        # Retry policy, timeout policy
```

Support providers:

- Ollama
- LM Studio
- Any OpenAI-compatible endpoint

### Success Criteria

- No module-level `OpenAI()` initialization
- `LLMClientFactory.create(config)` as entry point
- Retry on transient failures (configurable, default 3)
- Fallback to secondary model on primary failure
- All LLM interactions log: model, provider, latency, token count
- Unit tests for router do not require live LLM

### Estimated Effort: 3–4 days

---

## Phase 3 — Architecture Cleanup (Service Layer)

**Priority:** High. The UI god-module problem actively prevents all other improvements.

### Problem

`src/app.py` (876 lines) owns all orchestration. It duplicates generator, vision, and healer logic. The actual agent modules are bypassed.

### Deliverables

Extract a service layer that the UI calls:

```text
src/services/
├── __init__.py
├── generation_service.py   # Wraps generator agent; provides streaming callbacks
├── vision_service.py       # Wraps vision agent; provides streaming callbacks
└── healing_service.py      # Wraps healer agent; provides streaming callbacks
```

Reduce `src/app.py` to UI wiring only (target: under 200 lines).

Delete from `app.py`:

- `safe_generate_test()` — wire to `generation_service`
- `safe_run_test()` — wire to `generation_service`
- `safe_analyze_visual()` — wire to `vision_service`
- Inline healing loop in `wrap_healer()` — wire to `healing_service`

### Success Criteria

- `app.py` under 200 lines
- No `subprocess` calls in `app.py`
- No LLM calls in `app.py`
- No agent-module imports in `app.py` (imports only from `src/services/`)
- All existing functionality preserved

### Estimated Effort: 2–3 days

---

## Phase 4 — Healer Decomposition

**Priority:** High. Prerequisite for AST repair and better testability.

### Problem

`healer.py` is a god module mixing: runner, evidence collection, heuristics, LLM analysis, string patching, verification, and artifact emission.

### Deliverables

```text
src/healing/
├── __init__.py
├── runner.py          # run_test() — subprocess management
├── evidence.py        # gather_evidence() — logs, screenshots, DOM
├── classifier.py      # classify_failure_heuristic()
├── planner.py         # analyze_and_plan() — LLM reasoning
├── repair.py          # apply_fix() — initially string, then AST
├── verifier.py        # post-fix test run and pass/fail verdict
└── artifact_store.py  # emit_artifacts()
```

Healing orchestration (`attempt_healing()`) moves to `src/services/healing_service.py`.

### Success Criteria

- Each module has a single responsibility
- Each module is independently testable without running the others
- `healer.py` becomes a thin compatibility shim, then is deleted

### Estimated Effort: 2–3 days

---

## Phase 5 — AST-Based Repair

**Priority:** High. Prerequisite for structural fixes (add import, rename locator, restructure assertion).

### Problem

`apply_fix()` is string surgery. Structural changes (add import, rename across file, change call signature) require rewriting all matched text manually. Fragile to whitespace and indentation.

### Prerequisite

Complete `docs/ast-evaluation.md` before implementation. Evaluate: ts-morph, Babel, tree-sitter, SWC.

### Deliverables

```text
docs/ast-evaluation.md      # Tool comparison and decision
src/healing/repair.py       # AST-based implementation
```

AST repair operations to support (minimum viable):

- Selector replacement (`locator('X')` → `locator('Y')`)
- Import addition
- Timeout value adjustment
- `getByRole` argument correction
- Assertion operator swap

### Success Criteria

- `apply_fix()` uses AST for all structural repairs
- String fallback retained only for unrecognized patterns (logged as warning)
- AST repair tested with representative broken test fixtures
- No regression in existing `unit_test_fixer.py` cases

### Estimated Effort: 5–8 days

---

## Phase 6 — Context Collection Modernization

**Priority:** Medium. Improves generation and healing quality.

### Problem

Context for generation and healing is limited to raw HTML (stripped by BeautifulSoup). Playwright can provide richer signals.

### Deliverables

```text
src/context/
├── __init__.py
├── dom.py              # HTML snapshot (current)
├── accessibility.py    # Playwright accessibility tree
├── screenshot.py       # Screenshot capture (extracted from vision.py)
├── console.py          # Console errors during page load
├── network.py          # Failed network requests
├── locator_candidates.py  # Top candidate locators from a11y tree
└── collector.py        # Unified ContextSnapshot builder
```

### Success Criteria

- `ContextSnapshot` Pydantic model captures all context types
- Generator and healer consume context via `collector.py`
- Accessibility tree used for locator candidate extraction
- Console and network errors included in healer evidence
- Screenshot extraction moved from `vision.py` to `context/screenshot.py`

### Estimated Effort: 3–4 days

---

## Phase 7 — Evaluation Framework

**Priority:** High. Without this, no change can be validated as an improvement.

### Problem

No way to measure if a model or prompt change improved generation or healing quality. No datasets. No reproducibility.

### Deliverables

```text
benchmarks/
├── __init__.py
├── generation/
│   ├── fixtures/        # Input URLs + stories + expected outputs
│   └── runner.py        # Run generation benchmark
├── healing/
│   ├── fixtures/        # Broken test files + expected repairs
│   └── runner.py        # Run healing benchmark
├── intent_validation/
│   ├── fixtures/        # Generated tests + intent assertions
│   └── runner.py
├── mutations/
│   └── mutator.py       # Introduce known failures to generate healing fixtures
├── datasets/
│   └── README.md        # Dataset format specification
└── reports/
    └── .gitkeep
```

Every benchmark run records:

- Model + model version
- Prompt name + prompt version (hash)
- Temperature + seed
- Dataset version
- Timestamp
- Per-example pass/fail
- Aggregate metrics

### Success Criteria

- Benchmark runs are reproducible (same inputs → same outputs at temperature 0)
- Generation benchmark: measures selector quality, test structure, runnable rate
- Healing benchmark: measures fix success rate, failure classification accuracy
- Results exportable to JSON for comparison
- CI can run benchmarks against a dataset subset

### Estimated Effort: 5–7 days

---

## Phase 8 — Observability

**Priority:** Medium. Needed to understand production behavior and cost.

### Problem

No trace IDs. No token usage tracking. No latency metrics. No retry counts. Impossible to debug LLM failure patterns across runs.

### Prerequisite

Evaluate OpenTelemetry vs Langfuse before implementation. See `decisions.md`.

### Deliverables

Extend artifact schema:

```python
class TraceMetadata(BaseModel):
    trace_id: str
    operation_id: str
    model: str
    model_version: str
    prompt_version: str
    prompt_hash: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    retry_count: int
    failure_reason: Optional[str]
```

Instrument:

- Every LLM call
- Every Playwright subprocess invocation
- Evidence collection duration
- End-to-end healing session

### Success Criteria

- Every LLM call has a trace ID linkable to a healing session
- Token usage reported per run
- Latency tracked at each pipeline stage
- Retry counts visible in artifacts
- Local trace viewer (Langfuse or OTEL stdout exporter) works without cloud dependency

### Estimated Effort: 3–4 days

---

## Phase 9 — Explainability

**Priority:** Medium. The current `HealingDecision` is a good start; needs extension.

### Problem

`HealingDecision` captures reasoning steps and hypothesis but is missing: model metadata, prompt version, confidence rationale, and root cause evidence linkage.

### Deliverables

Extend `HealingDecision` (or its Pydantic replacement) with:

- `model_used: str`
- `prompt_version: str`
- `prompt_hash: str`
- `confidence_rationale: str`
- `root_cause_evidence: list[str]`
- `execution_duration_ms: int`
- `context_snapshot_id: str`

Extend `HealingDecision.to_markdown()` to surface new fields.

### Success Criteria

- Every healing artifact answers: which model, which prompt, how long, why confident
- Markdown report is human-readable without opening the JSON
- Explainability fields validated by Pydantic schema

### Estimated Effort: 1–2 days

---

## Phase 10 — AI Engineering Workbench (UI Reposition)

**Priority:** Low. Foundations must be complete first.

### Problem

The UI is currently a Gradio demo. It should become a tool engineers use to explore benchmarks, inspect artifacts, and compare model behavior.

### Deliverables

New UI tabs / panels:

- **Benchmark Explorer** — run and compare benchmark results
- **Artifact Inspector** — browse `tests/artifacts/` with full decision tree view
- **Trace Inspector** — view OpenTelemetry spans per session
- **Generation Visualizer** — show context snapshot alongside generated test
- **Healing Visualizer** — show evidence, classification, repair, verification side-by-side

Remove or deprioritize:

- SaaS-style UX patterns
- Marketing language in UI headers
- Features that obscure the engineering pipeline

### Estimated Effort: 4–6 days

---

## Phase 11 — Documentation Modernization Sprint

**Priority:** Medium. Implementation work through Phase 9 is substantially complete; the codebase now needs documentation that matches its maturity.

### Problem

The existing documentation was written incrementally during implementation. It is fragmented, inconsistently detailed, and does not give a new engineer a coherent mental model of the system. A senior engineer joining the project cannot understand the architecture, evaluate the design decisions, or contribute without reading source code.

### Audience

- Senior QA Engineers
- SDETs
- AI Engineers
- LLM Application Developers
- Researchers studying AI Systems Engineering

### Documentation Principles

Documentation must:

- Describe reality, not aspirations
- Match the current implementation exactly
- Be technically accurate
- Be beginner-friendly where possible
- Explain engineering decisions and tradeoffs
- Explain why choices were made, not just what they are

Avoid:

- Marketing language or buzzwords
- Unsupported claims
- Future roadmap items presented as implemented

### Sub-Phases

#### D1 — Repository Documentation Audit

Full audit of all existing documentation before any rewrites.

**Deliverable:** `docs/documentation-audit.md`

For every document identify: outdated content, missing content, incorrect content, redundant content, and recommended changes.

Documents to audit: `README.md`, `docs/architecture-review.md`, `docs/modernization-plan.md`, `docs/progress.md`, `docs/decisions.md`, `docs/technical-debt.md`, `docs/scorecard.md`, benchmark documentation, prompt documentation.

#### D2 — Rewrite README

The README becomes the primary entry point for all audiences.

**Deliverable:** `README.md` (complete rewrite)

Sections:

- Project Overview — what the project is
- Why It Exists — problem statement
- Core Capabilities — Test Generation, Test Healing, Structured Outputs, Evaluation Framework, AST-Based Repair, Explainability, Observability, Local LLM Support
- Architecture Overview — high-level diagram
- Quick Start — installation
- Running Locally — common workflows
- Evaluation System — how benchmarks work
- Repository Structure — important directories
- Technology Choices — why each major technology was selected
- Roadmap — current maturity and future plans

#### D3 — Architecture Documentation

One document per major subsystem. Every document must include: Purpose, Inputs, Outputs, Sequence Diagram, Data Flow, Design Decisions, Tradeoffs.

**Deliverables:**

```text
docs/architecture/
├── overview.md            # System-level architecture, component map
├── generation.md          # Context collection → prompt → LLM → validation → .spec.ts
├── healing.md             # Failure → classify → plan → repair → verify → artifact
├── evaluation.md          # Dataset → benchmark → model → scoring → report
├── llm-layer.md           # Router, client factory, registry, retry/fallback policies
├── observability.md       # Tracer, thread-local sessions, JSONL spans, querying
└── context-collection.md  # Browser session, a11y tree, DOM, console, network, locators
```

#### D4 — AI Systems Engineering Guide

This project as a reference implementation for AI Systems Engineering concepts.

**Deliverable:** `docs/ai-systems-engineering.md`

Topics: Structured Outputs, Model Routing, Evaluation Frameworks, Deterministic vs AI Repair, Explainability, Observability, Reproducibility. The goal is that a reader learns AI Systems Engineering patterns by studying this project.

#### D5 — Evaluation Documentation

**Deliverables:**

```text
docs/evaluation/
├── datasets.md            # Dataset format, mutation engine, fixture schema
├── benchmarks.md          # Benchmark methodology, runner design, metric definitions
├── scoring.md             # Scoring criteria, pass/fail logic, aggregate metrics
├── reproducibility.md     # Temperature 0, seed, prompt hash, dataset version
└── model-comparison.md    # How to run and compare models across benchmark runs
```

#### D6 — Prompt Documentation

**Deliverables:**

```text
docs/prompts/
├── overview.md            # Prompt management strategy, manifest.json, versioning
├── generation.md          # Generator prompt: inputs, outputs, format contract
├── healing.md             # Healer prompt: inputs, outputs, repair strategy guide
├── intent-validation.md   # Intent validation prompt (if applicable)
└── versioning.md          # How to version prompts, when to increment, hash vs version
```

#### D7 — Developer Documentation

A new contributor should be able to run the project, add a model, add a benchmark, add a repair strategy, and debug failures without reading source code.

**Deliverables:**

```text
docs/development/
├── setup.md               # Prerequisites, installation, environment variables
├── testing.md             # Running unit tests, test patterns, mocking LLM/browser
├── debugging.md           # Common failure modes, trace inspection, log reading
├── adding-models.md       # How to add a new LLM provider or model to the registry
├── adding-benchmarks.md   # How to create a benchmark dataset and runner
└── adding-healing-strategies.md  # How to add a new RepairStrategy and AST handler
```

#### D8 — Architecture Decision Records Review

Review all existing ADRs in `docs/decisions.md` for accuracy. Ensure every major decision is documented. Create ADRs where missing.

**ADRs to verify or create:**

- LiteLLM adoption (or rejection — see ADR-002/007)
- Pydantic adoption for structured outputs
- AST strategy selection (ts-morph — see ADR-003)
- Evaluation framework design (pure functions, no live LLM)
- Observability approach (custom JSONL vs OpenTelemetry vs Langfuse)
- Context collection architecture (single browser session)
- Thread-local session isolation for Gradio

#### D9 — Visual Documentation

Mermaid diagrams for all major flows, embedded in the relevant architecture documents.

**Diagrams required:**

- System Architecture: `UI → Services → Pipelines → LLM Layer → Evaluation → Artifacts`
- Generation Flow: `Context Collection → Prompt Assembly → Structured Output → Validation → Test Generation`
- Healing Flow: `Failure → Classification → Planning → Repair → Verification → Artifact`
- Evaluation Flow: `Dataset → Benchmark → Model → Scoring → Report`
- Observability Flow: `Session Start → LLM Span → Subprocess Span → Session End → JSONL`

#### D10 — Documentation Quality Review

Final verification pass before closing the sprint.

**Verify:**

- All code examples are syntactically correct
- All CLI commands work against the actual project
- All file paths exist in the repository
- All architecture diagrams match the implementation
- All cross-references between documents are valid

**Remove:**

- Outdated documentation that no longer reflects the implementation
- Duplicate content across documents
- Contradictory claims between documents

### Success Criteria

A new engineer can answer the following without reading implementation code:

- What is this project and why was it built?
- How does test generation work end-to-end?
- How does self-healing work end-to-end?
- How are models evaluated?
- How does observability work?
- How do I add a new model?
- How do I add a new benchmark?
- How do I contribute a bug fix or new feature?

### Estimated Effort: 5–8 days

---

## Milestone Summary

| Phase | Name | Priority | Effort | Depends On |
| --- | --- | --- | --- | --- |
| 1 | Structured Outputs | CRITICAL | 3–5d | — |
| 2 | LLM Layer | HIGH | 3–4d | Phase 1 |
| 3 | Architecture Cleanup | HIGH | 2–3d | Phase 1 |
| 4 | Healer Decomposition | HIGH | 2–3d | Phase 3 |
| 5 | AST Repair | HIGH | 5–8d | Phase 4 |
| 6 | Context Collection | MEDIUM | 3–4d | Phase 3 |
| 7 | Evaluation Framework | HIGH | 5–7d | Phases 1–4 |
| 8 | Observability | MEDIUM | 3–4d | Phase 2 |
| 9 | Explainability | MEDIUM | 1–2d | Phases 1, 8 |
| 10 | UI Reposition | LOW | 4–6d | Phases 3–9 |
| 11 | Documentation Modernization | MEDIUM | 5–8d | Phases 1–10 |

**Total estimated effort:** 36–58 days of focused engineering work.

---

## No New Feature Rule

Until the following are true, no new user-facing capabilities will be added:

- [ ] Structured outputs complete (Phase 1)
- [ ] Evaluation framework exists (Phase 7)
- [ ] Healing uses AST transformations (Phase 5)
- [ ] Architecture boundaries cleaned up (Phases 3–4)

Foundations before features.
