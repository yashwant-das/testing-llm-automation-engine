# Progress

> Updated after every completed milestone.
> Format: [DATE] — STATUS — Description

---

## Current Status

**Phase:** Phase 5 — AST-Based Repair (COMPLETE)
**Next Phase:** Phase 6 — Context Collection
**Blockers:** None

---

## Completed Work

### 2026-06-06 — Phase 0: Repository Audit ✅

Full audit of all source files, tests, prompts, and documentation.

**Files audited:**

- `src/app.py` (876 lines)
- `src/agents/generator.py`, `healer.py`, `vision.py`
- `src/models/healing_model.py`
- `src/utils/llm.py`, `browser.py`, `validation.py`, `formatting.py`, `prompt_loader.py`
- `prompts/generator.md`, `healer.md`, `vision.md`
- `tests/unit_test_*.py` (4 files)
- `requirements.txt`, `pyproject.toml`, `playwright.config.ts`

**Key findings:**

- UI god module: `app.py` duplicates all agent logic
- No structured outputs: regex + brace-slice JSON parsing
- String-based repair: `apply_fix()` is sliding-window text replacement
- No evaluation framework
- No observability
- Module-level LLM singleton blocks testability

**Documentation created:**

- `docs/architecture-review.md` — full findings with severity ratings
- `docs/modernization-plan.md` — 10-phase plan with estimates
- `docs/progress.md` — this file
- `docs/decisions.md` — ADR template, initial decisions
- `docs/backlog.md` — deferred ideas
- `docs/technical-debt.md` — full debt register
- `docs/scorecard.md` — baseline maturity scores

### 2026-06-06 — Phase 1: Structured Outputs Foundation ✅

All LLM response parsing migrated to Pydantic. Dead code deleted. 69/69 tests passing.

**Files created:**

- `schemas/__init__.py`, `shared.py`, `healing.py`, `generation.py`, `evaluation.py`, `artifacts.py`
- `tests/unit_test_schemas.py` — 41 new tests

**Files updated:**

- `src/utils/llm.py` — added `parse_llm_response()`; `extract_json/code_block` moved to internal `_` helpers
- `src/agents/healer.py` — `extract_json_block` + `json.loads` replaced with `parse_llm_response(HealingAnalysis)`; `TestRunResult` replaced with `RunResult`
- `src/agents/generator.py` — internal `GenerationResult` validation on LLM code extraction
- `src/agents/vision.py` — internal `GenerationResult` validation on LLM code extraction
- `src/models/healing_model.py` — converted to re-export shim from `schemas/`
- `tests/unit_test_fixer.py` — updated to expect `ValidationError` for invalid enum values (correct Pydantic behavior)
- `tests/unit_test_validation.py` — removed `sanitize_for_shell` tests (dead code deleted)
- `pyproject.toml` — `pydantic>=2.0.0` added as explicit dependency

**Deleted:**

- `sanitize_for_shell()` from `src/utils/validation.py` — dead code (TD-013 resolved)

**Debt resolved:** TD-002 (fragile parsing), TD-006 (dataclasses), TD-013 (dead code), TD-015 (TestRunResult mock)

---

### 2026-06-06 — Phase 2: LLM Layer Modernization ✅

Module-level `OpenAI()` singleton eliminated. All LLM calls route through `LLMRouter`. 129/129 tests passing.

**Files created:**

- `src/llm/__init__.py` — public API; `get_default_router()` lazy singleton
- `src/llm/client.py` — `ProviderConfig`, `LLMClientFactory` (no module-level side effects)
- `src/llm/registry.py` — `ModelCapabilities`, `ModelRegistry`
- `src/llm/policies.py` — `RetryPolicy`, `TimeoutPolicy`
- `src/llm/router.py` — `LLMRequest`, `LLMResponse`, `LLMRouter`
- `tests/unit_test_llm.py` — 60 new tests (zero live LLM calls)

**Files updated:**

- `src/utils/llm.py` — module-level `OpenAI()` block deleted; `get_client()` / `get_model()` are now deprecated shims that delegate to `LLMClientFactory` / `LLMRouter`
- `src/agents/healer.py` — `get_client()` / `get_model()` replaced with `get_default_router().complete_primary()`
- `src/agents/generator.py` — same migration
- `src/agents/vision.py` — `get_client()` / `get_model(vision=True)` replaced with `get_default_router().complete_vision()`
- `docs/decisions.md` — ADR-002 superseded by ADR-007 (no LiteLLM)

**Debt resolved:** TD-008 (module-level LLM singleton)

---

### 2026-06-06 — Phase 3: Architecture Cleanup (Service Layer) ✅

`app.py` reduced from 875 lines to 199 lines. All orchestration logic extracted to `src/services/`.
129/129 tests passing.

**Files created:**

- `src/services/__init__.py` — package documentation
- `src/services/generation_service.py` — `generate_test_streaming`, `run_test_streaming`
- `src/services/vision_service.py` — `analyze_visual_streaming`, `run_vision_test_streaming`
- `src/services/healing_service.py` — `heal_test_streaming` (full healing loop with streaming)

**Files updated:**

- `src/app.py` — rewritten to 199 lines of pure Gradio layout + button wiring
- `src/utils/llm.py` — stale `extract_code_block` docstring updated (no remaining callers)

**Verified (app.py):**

- No `subprocess` calls
- No LLM calls (`get_client`, `get_model`, `extract_code_block`)
- No agent-module imports (`from src.agents.*`)
- Imports only from `src/services/`

---

## Current Work

---

### 2026-06-06 — Phase 4: Healer Decomposition ✅

`healer.py` (471 lines, 8 mixed-responsibility functions) decomposed into a
`src/healing/` package with 7 single-responsibility modules.  170/170 tests passing.

**Files created:**

- `src/healing/__init__.py` — public API re-exports + `attempt_healing()` non-streaming CLI orchestrator
- `src/healing/runner.py` — `run_test()` subprocess management
- `src/healing/evidence.py` — `extract_url_from_code()` + `gather_evidence()`
- `src/healing/classifier.py` — `classify_failure_heuristic()`
- `src/healing/planner.py` — `analyze_and_plan()` heuristic + LLM reasoning
- `src/healing/repair.py` — `apply_fix()` indentation-tolerant string replacement
- `src/healing/verifier.py` — `verify_repair()` post-repair test execution
- `src/healing/artifact_store.py` — `emit_artifacts()` JSON persistence
- `tests/unit_test_healing.py` — 41 new tests (zero live LLM calls, mocked subprocess)

**Files updated:**

- `src/agents/healer.py` — reduced to 40-line compatibility shim (re-exports from `src.healing`)
- `src/services/healing_service.py` — imports from `src.healing` directly; uses `verify_repair()`
- `tests/unit_test_fixer.py` — imports from `src.healing.repair` and `src.healing.evidence`
- `tests/unit_test_classification.py` — imports from `src.healing.classifier`

**Verified constraints:**

- Each module has a single responsibility
- Each module is independently importable and testable
- Zero cross-module side effects at import time
- `healer.py` is now a thin shim (will be deleted in Phase 5)

**Debt resolved:** TD-001 partial (healer god module), TD-003 (mixed subprocess/LLM/IO concerns)

---

### 2026-06-06 — Phase 5: AST-Based Repair ✅

`apply_fix()` upgraded from string-only surgery to AST-first with string fallback.
ts-morph selected as the AST tool (see `docs/ast-evaluation.md` and ADR-003).
205/205 tests passing.

**Files created:**

- `docs/ast-evaluation.md` — full tool evaluation (ts-morph vs Babel vs tree-sitter vs SWC)
- `scripts/ast_repair.js` — Node.js ts-morph script; 5 strategies; JSON stdin/stdout protocol
- `tests/fixtures/broken_selector.spec.ts` — fixture: selector drift (2 occurrences)
- `tests/fixtures/broken_timeout.spec.ts` — fixture: timeout too short
- `tests/fixtures/broken_import.spec.ts` — fixture: missing import
- `tests/fixtures/broken_assertion.spec.ts` — fixture: wrong assertion method
- `tests/unit_test_ast_repair.py` — 35 new tests (routing, integration, regression)

**Files updated:**

- `schemas/healing.py` — added `RepairStrategy` enum; `HealingAction.repair_strategy` field
  (default `STRING_REPLACE` — backward-compatible with all existing artifacts)
- `schemas/__init__.py` — export `RepairStrategy`
- `src/healing/repair.py` — AST path in `apply_fix()`; string path extracted to
  `_apply_string_fix()`; `_apply_ast_fix()` calls `scripts/ast_repair.js` via subprocess
- `prompts/healer.md` — `repair_strategy` field added to output schema with strategy
  selection guidance
- `docs/decisions.md` — ADR-003 updated from UNDER INVESTIGATION → DECIDED
- `package.json` — `ts-morph` added to dependencies

**AST repair strategies (MVP):**

- `selector_replace` — replaces ALL occurrences of a locator selector file-wide
- `import_add` — inserts missing import; merges named imports if module already present
- `timeout_adjust` — updates `{ timeout: N }` property values
- `role_argument` — updates `name` option in `getByRole()` calls
- `assertion_swap` — renames assertion methods in `expect()` chains

**Fallback policy:**

1. Strategy is `string_replace` → skip subprocess, use string path directly
2. AST changes: 0 → warn + fall back to string
3. Node.js timeout / FileNotFoundError / bad JSON → warn + fall back to string
4. String also fails → return unchanged code, log warning

**Debt resolved:** TD-003 (string-based repair)

---

## Upcoming Work

| Phase | Description | Status |
| --- | --- | --- |
| Phase 1 | Structured Outputs Foundation | COMPLETE |
| Phase 2 | LLM Layer Modernization | COMPLETE |
| Phase 3 | Architecture Cleanup (Service Layer) | COMPLETE |
| Phase 4 | Healer Decomposition | COMPLETE |
| Phase 5 | AST-Based Repair | COMPLETE |
| Phase 6 | Context Collection | NEXT |
| Phase 7 | Evaluation Framework | PENDING |
| Phase 8 | Observability | PENDING |
| Phase 9 | Explainability | PENDING |
| Phase 10 | UI Reposition | PENDING |

---

## Blockers

None currently.

---

## Decisions Log

See `decisions.md` for all Architecture Decision Records.

---

## Metrics

| Metric | Baseline (2026-06-06) | Target |
| --- | --- | --- |
| Scorecard total | 27/100 | 75/100 |
| LLM parse fragility (critical paths) | 4 fragile parsers | 0 |
| App.py line count | 876 | <200 |
| Benchmark datasets | 0 | 3+ |
| Observability coverage | 0% | 80%+ |
| Test coverage (meaningful) | 4 unit tests | 50+ tests |
