# Repository Maturity Scorecard

> Baseline established: 2026-06-06 (Phase 0 audit complete)
> Score range: 0–10 per category
> Updated after each major milestone

---

## Baseline Scores — 2026-06-06

| Category | Score | Target |
| --- | --- | --- |
| Structured Outputs | 1 | 9 |
| Evaluation Framework | 0 | 8 |
| Observability | 1 | 8 |
| Explainability | 4 | 8 |
| Determinism | 3 | 8 |
| Local LLM Support | 5 | 9 |
| Architecture | 3 | 8 |
| Documentation | 4 | 9 |
| Testing | 3 | 8 |
| Maintainability | 3 | 8 |
| **Total** | **27/100** | **83/100** |

---

## Category Explanations

### Structured Outputs — 1/10

**Current state:**

- LLM responses parsed with regex (`extract_code_block`) and brace-slicing (`extract_json_block`)
- No Pydantic schema enforcement
- No OpenAI `response_format` or tool-call structured output
- `json.loads()` called directly on extracted strings with no validation
- Schema in `healer.md` prompt and `HealingDecision` dataclass are not linked — drift is invisible

**Why 1 (not 0):** The `HealingDecision` dataclass exists and provides a partial schema contract. JSON artifacts are consistently structured. The healer prompt explicitly defines the expected JSON shape.

**Path to 9:** Pydantic `BaseModel` schemas in `schemas/`, OpenAI structured output mode, retry on validation failure, schema tests.

---

### Evaluation Framework — 0/10

**Current state:**

- 4 unit test files covering: failure classification heuristics, JSON extraction, fix application, input validation
- No benchmark datasets
- No model comparison capability
- No prompt comparison capability
- No regression detection
- No reproducibility guarantees

**Why 0:** Unit tests are necessary but do not constitute an evaluation framework. There is no way to answer "did this change improve results?" — the core question an evaluation framework answers.

**Path to 8:** `benchmarks/` directory with labeled datasets (broken tests, expected repairs), benchmark runner, result storage, and comparison tooling.

---

### Observability — 1/10

**Current state:**

- `ExecutionTimeline` JSON artifact captures step names and timestamps
- `HealingDecision` JSON artifact captures failure type and evidence
- No trace IDs
- No token usage tracking
- No latency measurement
- No retry count recording
- Artifacts are files on disk, not queryable

**Why 1 (not 0):** The JSON artifacts provide basic after-the-fact inspection. The execution timeline is a genuine (if primitive) audit trail.

**Path to 8:** OpenTelemetry instrumentation on all LLM calls and subprocess invocations; token usage, latency, and retry count in every artifact; optional Langfuse integration for UI.

---

### Explainability — 4/10

**Current state:**

- `HealingDecision` captures: failure type, failure summary, hypothesis, confidence score, reasoning steps, action taken (original and fixed code, description)
- Evidence includes: error log, screenshot path, DOM snippet
- `to_markdown()` generates human-readable report
- Gradio UI surfaces explainable report tab and raw JSON accordion

**Why 4:** The explainability story for healing is the strongest part of the current system — it clearly shows what failed, why, and what was done. Losing points for: no model metadata in artifacts, no prompt version in artifacts, no confidence rationale, no root cause evidence linkage.

**Path to 8:** Add model used, prompt version/hash, confidence rationale, execution duration, and root cause evidence to `HealingDecision`. Generation artifacts are currently unexplainable — address that.

---

### Determinism — 3/10

**Current state:**

- Temperature set to 0.1 (low but not zero) for all LLM calls
- No seed parameter used
- Heuristic classifier is fully deterministic (regex patterns)
- `apply_fix()` string matching is deterministic given identical input
- No dataset version tracking
- Results are not reproducible in the strict sense

**Why 3:** The heuristic classifier is a genuine deterministic component. Temperature 0.1 is mostly deterministic in practice. The hybrid approach (heuristics first, then LLM) adds some determinism.

**Path to 8:** Seed parameter on all LLM calls, temperature 0.0 as default, model+version+seed+prompt\_hash recorded per run, benchmark results reproducible.

---

### Local LLM Support — 5/10

**Current state:**

- LM Studio and Ollama both supported via OpenAI-compatible endpoint
- Provider selection via `LLM_PROVIDER` env var
- Model names configurable via env vars
- Default Ollama model: `gemma4:26b`
- No model capability metadata
- No fallback if local LLM is unavailable
- No health check before session start
- Documentation exists for setup

**Why 5:** Both major local LLM providers work. The implementation is functional and documented. Losing points for: no capability registry, no fallback, no health check, no LiteLLM routing layer.

**Path to 9:** LiteLLM router, model capability registry, health check at startup, graceful fallback to alternative model.

---

### Architecture — 3/10

**Current state:**

- Three agent modules exist with appropriate names
- Agent modules are largely bypassed by the UI
- `app.py` is 876 lines and owns all orchestration
- No service layer
- Healer is a god module mixing 7 responsibilities
- No established boundaries between layers
- Dataclasses instead of Pydantic for models
- Module-level singleton initialization

**Why 3:** The agent/utils/models directory structure is correct. The overall pipeline concept (generate → run → fail → heal → verify) is sound and documented. The implementation of that structure is deeply compromised by the UI owning orchestration.

**Path to 8:** Service layer (Phase 3), healer decomposition (Phase 4), Pydantic models (Phase 1), no module-level side effects.

---

### Documentation — 4/10

**Current state (before this audit):**

- `README.md` (13,576 bytes) — comprehensive setup and usage docs
- `docs/ARCHITECTURE.md` — good pipeline explanation
- `docs/DEMO_GUIDE.md` — demo walkthrough
- `docs/HEALING_SCENARIOS.md` — healing examples
- `DOCKER.md`, `ENV_VARIABLES.md`, `AGENTS.md` — operational docs
- No architecture decision records
- No modernization plan
- No technical debt register
- No scorecard

**After Phase 0 audit:**

- `docs/architecture-review.md` ✅ (this session)
- `docs/modernization-plan.md` ✅ (this session)
- `docs/progress.md` ✅ (this session)
- `docs/decisions.md` ✅ (this session)
- `docs/technical-debt.md` ✅ (this session)
- `docs/backlog.md` ✅ (this session)
- `docs/scorecard.md` ✅ (this session)
- Missing: `docs/ast-evaluation.md` (Phase 5 prerequisite)

**Why 4:** The existing docs are high quality for user-facing concerns. Losing points for: no ADRs, no debt tracking, no progress tracking, no scorecard. The new files created in this session will raise this score substantially when the next scorecard is taken.

**Path to 9:** Maintain all tracking files continuously; add `docs/ast-evaluation.md`; keep `progress.md` updated after every milestone.

---

### Testing — 3/10

**Current state:**

- 4 unit test files (classification, fixer, json, validation)
- Tests are well-written and cover real behavior
- No integration tests
- No end-to-end test harness
- No benchmark tests
- No test isolation (some tests import from agent modules that have module-level side effects)
- `pyproject.toml` has no pytest configuration

**Why 3:** The unit tests that exist are good and test real behavior (not trivial mocks). Losing points for: no integration tests, no benchmarks, no isolation (module singleton leaks into tests), tiny coverage surface area.

**Path to 8:** Schema tests (Phase 1), isolated unit tests after singleton removal (Phase 2), healing benchmark fixtures (Phase 7), integration test harness.

---

### Maintainability — 3/10

**Current state:**

- Ruff linting and formatting configured
- ESLint + Prettier for TypeScript
- Husky pre-commit hooks
- No type hints on several functions
- Module-level side effects complicate imports
- God module (`app.py`) — any change risks regression anywhere in the UI
- Logic duplication means bug fixes must be applied twice
- No CI pipeline defined

**Why 3:** The linting and formatting toolchain is excellent — this is often neglected and the project gets it right. Losing points for: god module, no CI, module side effects, duplication.

**Path to 8:** Service layer extraction reduces god module risk; CI pipeline adds automated safety net; module side effect removal improves import safety.

---

## Post-Phase 10 Scores — 2026-06-06

| Category | Score | Change |
| --- | --- | --- |
| Structured Outputs | 9 | +8 (Phases 1, 9) |
| Evaluation Framework | 8 | +8 (Phase 7) |
| Observability | 8 | +7 (Phase 8) |
| Explainability | 8 | +4 (Phase 9) |
| Determinism | 8 | +5 (Phases 2, 5, 7, 9) |
| Local LLM Support | 8 | +3 (Phase 2) |
| Architecture | 8 | +5 (Phases 2, 3, 4, 6) |
| Documentation | 7 | +3 (Phases 0, 10) |
| Testing | 8 | +5 (Phases 1, 7, 8, 9) |
| Maintainability | 8 | +5 (Phases 2, 3, 4) |
| **Total** | **80/100** | **+53** |

Note: Documentation held at 7 — the Phase 10 UI reposition added engineering tabs and improved the workbench, but the documentation suite itself was still pre-Phase 11.

---

## Post-Phase 11 Scores — 2026-06-06

| Category | Score | Change |
| --- | --- | --- |
| Structured Outputs | 9 | — |
| Evaluation Framework | 8 | — |
| Observability | 8 | — |
| Explainability | 8 | — |
| Determinism | 8 | — |
| Local LLM Support | 8 | — |
| Architecture | 8 | — |
| Documentation | 9 | +2 (Phase 11) |
| Testing | 8 | — |
| Maintainability | 8 | — |
| **Total** | **82/100** | **+2** |

Phase 11 improvements: README rewritten, full architecture docs (7 files with Mermaid diagrams), AI systems engineering guide, evaluation docs (5 files), prompt docs (4 files), developer docs (6 files), ADRs extended to ADR-011, technical debt fully resolved.

---

## Score History

| Date | Total | Notes |
| --- | --- | --- |
| 2026-06-06 | 27/100 | Baseline — Phase 0 audit complete |
| 2026-06-06 | 80/100 | Post-Phase 10 — UI reposition complete |
| 2026-06-06 | 82/100 | Post-Phase 11 — Documentation Modernization complete |

---

## Score Targets by Phase

| After Phase | Expected Score | Key Improvements |
| --- | --- | --- |
| Phase 1 | 38/100 | +8 structured outputs, +4 testing, +3 maintainability |
| Phase 2 | 46/100 | +4 local LLM, +3 determinism, +3 maintainability |
| Phases 3+4 | 55/100 | +8 architecture, +4 maintainability |
| Phase 5 | 62/100 | +5 determinism, +3 explainability |
| Phase 7 | 73/100 | +8 evaluation framework, +3 testing |
| Phases 8+9 | 80/100 | +7 observability, +4 explainability |
| Phase 10 | 80/100 | UI reposition — engineering workbench framing |
| Phase 11 | 82/100 | +2 documentation |
