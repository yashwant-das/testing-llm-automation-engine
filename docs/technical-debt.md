# Technical Debt Register

> Every item has: Severity, Description, Impact, Recommended Fix, Status.
> Updated as debt is introduced or resolved.
> Last updated: 2026-06-06 (Phase 11 documentation audit)

---

## Resolved

All 15 items from the Phase 0 audit have been resolved. Items are listed below with the phase that resolved them.

---

### TD-001: UI owns all orchestration logic ✅ RESOLVED — Phase 3

**Was:** `app.py` (876 lines) duplicated the entire generation, vision, and healing pipelines inline inside Gradio event handlers. The actual agent modules were bypassed or imported piecemeal.

**Fix:** `src/services/` layer introduced in Phase 3. `app.py` now imports only from `src/services/`. Services call agents. No agent imports in `app.py`. (See ADR-006.)

---

### TD-002: Fragile LLM response parsing ✅ RESOLVED — Phase 1

**Was:** All LLM responses parsed with regex and brace-slicing. `json.loads()` called directly with no schema validation. Silent data corruption on field name changes.

**Fix:** `parse_llm_response()` in `src/utils/llm.py` validates every LLM response against a Pydantic schema with retry on validation failure. `HealingDecision`, `Evidence`, `GenerationResult`, and `HealingAnalysis` are all Pydantic models. (See ADR-001.)

---

### TD-003: String-based test repair ✅ RESOLVED — Phase 5

**Was:** `apply_fix()` used exact string matching and sliding-window normalised line matching only. Structural repairs (add import, file-wide rename) were impossible.

**Fix:** `scripts/ast_repair.js` implements 5 AST strategies via ts-morph. `src/healing/repair.py` dispatches to AST first, falls back to string replacement, then to unchanged code. (See ADR-003.)

---

### TD-004: No evaluation framework ✅ RESOLVED — Phase 7

**Was:** No benchmark datasets, no reproducible evaluation runs, no way to measure improvement.

**Fix:** `benchmarks/` directory with labeled datasets, pure-function evaluators, `BenchmarkRun` and `BenchmarkRunConfig` Pydantic models, `run_healing_benchmark()` runner. 4 benchmark scenarios. Results in `tests/artifacts/`. (See ADR-009.)

---

### TD-005: No observability ✅ RESOLVED — Phase 8

**Was:** No trace IDs, no token usage, no latency metrics, no retry counts. JSON artifacts existed but were not linked by trace.

**Fix:** `src/observability/` tracer records `SessionSpan`, `TraceMetadata` (LLM), and `SubprocessSpan` to `logs/traces.jsonl`. Thread-local session isolation for Gradio. NullTracer default so all instrumentation points are safe before `configure_tracer()`. (See ADR-004, ADR-010.)

---

### TD-006: Python dataclasses instead of Pydantic models ✅ RESOLVED — Phase 1

**Was:** `HealingDecision`, `Evidence`, `HealingAction`, `ExecutionTimeline`, `TimelineStep` were `@dataclass`. No field validation, no schema export.

**Fix:** All models replaced with Pydantic `BaseModel` in `schemas/`. Field validators, coercion, and `model_validate_json()` used throughout. (See ADR-001.)

---

### TD-007: HTML-only context collection ✅ RESOLVED — Phase 6

**Was:** Page context was HTML stripped by BeautifulSoup only. Accessibility tree, console errors, network failures, and locator candidates were not collected.

**Fix:** `src/context/` provides 6 collector modules (dom, accessibility, locator_candidates, console, network, screenshot) sharing a single Playwright session. All context types included in `ContextSnapshot` and surfaced as `Evidence`. (See ADR-008.)

---

### TD-008: Module-level LLM singleton ✅ RESOLVED — Phase 2

**Was:** `client = OpenAI(...)` ran at import time. Any module import triggered client initialization. Unit tests required module-level patching or live LLM credentials.

**Fix:** `LLMClientFactory.create(config)` pattern in `src/llm/client.py`. No module-level side effects. `get_default_router()` is a lazy singleton initialised on first call, not on import. (See ADR-007.)

---

### TD-009: No retry or fallback policy ✅ RESOLVED — Phase 2

**Was:** Single LLM call with no retry. Transient failures propagated as successful values.

**Fix:** `LLMRouter` in `src/llm/router.py` implements configurable retry with exponential backoff via `RetryPolicy`. Fallback to secondary model on primary failure. All controlled by `RetryPolicy` and `TimeoutPolicy` Pydantic models. (See ADR-007.)

---

### TD-010: No model registry or capability metadata ✅ RESOLVED — Phase 2

**Was:** Model names were env var strings. No capability metadata. Provider selection was a hard-coded `if` branch.

**Fix:** `src/llm/registry.py` implements `ModelCapabilities` and `ModelRegistry`. Vision routing reads capability metadata before selecting the vision model. `ProviderConfig` in `src/llm/client.py` handles all provider-specific configuration. (See ADR-007.)

---

### TD-011: No prompt versioning ✅ RESOLVED — Phase 9

**Was:** Prompts loaded by name only. No version, no hash, no audit trail linking an artifact to the prompt that produced it.

**Fix:** `prompts/manifest.json` maps prompt names to human-set version labels. `get_prompt_hash()` computes SHA-256 of the prompt file content at call time (not cached — always reflects disk state). Both recorded in every `HealingDecision` artifact as `prompt_version` and `prompt_hash`. (See ADR-005.)

---

### TD-012: Evidence staleness in healer ✅ RESOLVED — Phase 6

**Was:** Healer fetched live DOM during healing — page state may differ from state at failure time.

**Fix:** `src/context/collect_context()` captures all 6 context types in a single Playwright session opened at the start of the healing run. Evidence is a snapshot from that session, not a re-fetch. `ContextSnapshot` is converted to `Evidence` fields once and passed through the pipeline. (See ADR-008.)

---

### TD-013: `sanitize_for_shell()` dead code ✅ RESOLVED — Phase 3

**Was:** `sanitize_for_shell()` defined in `src/utils/validation.py` but never called. All subprocess calls use list arguments.

**Fix:** Function and its tests deleted in Phase 3 cleanup.

---

### TD-014: Vision agent logic duplicated in app.py ✅ RESOLVED — Phase 3

**Was:** `safe_analyze_visual()` in `app.py` (160 lines) reimplemented the vision pipeline. `vision.py` was never called by the UI.

**Fix:** Vision service function in `src/services/` calls `src/agents/vision.py` directly. `app.py` calls the service. The duplicate 160-line implementation was deleted. (See ADR-006.)

---

### TD-015: `TestRunResult` mock class ✅ RESOLVED — Phase 1

**Was:** Hand-rolled `TestRunResult` class in `healer.py` mimicked `subprocess.CompletedProcess` for timeout/not-found cases. Inconsistent typing.

**Fix:** Replaced with `RunResult` Pydantic model in `schemas/shared.py`. Used consistently for both subprocess results and error fallbacks throughout the healing pipeline.
