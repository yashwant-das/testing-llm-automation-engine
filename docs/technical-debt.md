# Technical Debt Register

> Every item has: Severity, Description, Impact, Recommended Fix, Status.
> Updated as debt is introduced or resolved.
> Last updated: 2026-06-06

---

## CRITICAL

### TD-001: UI owns all orchestration logic

**Severity:** CRITICAL
**File:** `src/app.py` (876 lines)

**Description:**
`app.py` duplicates the entire generation, vision, and healing pipelines inline inside Gradio event handlers. The actual agent modules (`generator.py`, `vision.py`, `healer.py`) are either bypassed or imported piecemeal for their internals.

Specific violations:

- `safe_generate_test()` (97 lines): replicates `generator.generate_test_script()`
- `safe_run_test()` (104 lines): replicates `generator.run_generated_test()`
- `safe_analyze_visual()` (160 lines): replicates `vision.analyze_visual_ui()`
- `wrap_healer()` (260 lines): reimplements the entire healing loop from `healer.attempt_healing()`

**Impact:**

- Bug fixes must be applied in two places
- Agents cannot be tested independently of the UI
- Adding observability or structured outputs requires changes in two codebases
- New pipeline features must be implemented twice

**Recommended Fix:** Extract `src/services/` layer. UI calls service functions. Services call agents. (See ADR-006, Phase 3.)

**Status:** OPEN — Phase 3

---

### TD-002: Fragile LLM response parsing

**Severity:** CRITICAL
**Files:** `src/utils/llm.py` (`extract_json_block`, `extract_code_block`)

**Description:**
All LLM responses are parsed with regex and string manipulation:

- `extract_code_block()`: regex for markdown fence, fallback strips lines starting with "here", "sure", "certainly"
- `extract_json_block()`: regex for markdown fence, fallback takes first `{` to last `}` in the response string

Then `json.loads()` is called directly on the extracted string with no schema validation.

**Impact:**

- Silent data corruption when field names change
- Test breakage on model response format changes
- No retry on parse failure — errors surface as generic exceptions

**Recommended Fix:** Replace with Pydantic `model_validate_json()` on structured output responses. For code extraction, use OpenAI structured output mode to return code wrapped in a typed field. (See ADR-001, Phase 1.)

**Status:** OPEN — Phase 1

---

### TD-003: String-based test repair

**Severity:** CRITICAL
**File:** `src/agents/healer.py` — `apply_fix()`

**Description:**
`apply_fix()` implements two repair strategies:

1. Exact string match and replace
2. Sliding-window normalized (stripped whitespace) line match and replace

Neither strategy can handle structural repairs: adding imports, renaming a symbol across a file, changing test structure, or modifying multiple non-adjacent locations.

**Impact:**

- Structural failures (missing import, refactored API) cannot be healed
- Whitespace differences between LLM output and file content cause silent no-ops
- Complex repairs require the LLM to produce exact contiguous code blocks — fragile

**Recommended Fix:** Replace with ts-morph AST transformations for structural operations. Retain string fallback for trivial single-line changes. (See ADR-003, Phase 5.)

**Status:** OPEN — Phase 5

---

## HIGH

### TD-004: No evaluation framework

**Severity:** HIGH

**Description:**
There is no way to measure whether a model change, prompt change, or algorithm change improved results. No benchmark datasets exist. No reproducible evaluation runs exist.

**Impact:**

- Cannot validate improvements scientifically
- Cannot detect regressions
- Cannot compare models or prompts

**Recommended Fix:** Build `benchmarks/` directory with datasets, runners, and result storage. (Phase 7.)

**Status:** OPEN — Phase 7

---

### TD-005: No observability

**Severity:** HIGH

**Description:**
No trace IDs, no token usage tracking, no latency metrics, no retry counts, no failure pattern analysis. JSON artifacts exist per run but are not queryable or linked by trace.

**Impact:**

- Cannot debug LLM failure patterns
- Cannot optimize cost
- Cannot identify which pipeline stage is slow

**Recommended Fix:** Instrument all LLM calls and Playwright subprocess calls with OpenTelemetry. (Phase 8.)

**Status:** OPEN — Phase 8

---

### TD-006: Python dataclasses instead of Pydantic models

**Severity:** HIGH
**File:** `src/models/healing_model.py`

**Description:**
`HealingDecision`, `Evidence`, `HealingAction`, `ExecutionTimeline`, `TimelineStep` are all `@dataclass`. Manual `__post_init__` coercion for `FailureType`. No field validation, no JSON schema export, no integration with OpenAI `response_format`.

**Impact:**

- Cannot use Pydantic schema for OpenAI structured output enforcement
- Runtime errors on invalid data instead of validation errors
- No schema documentation generated automatically

**Recommended Fix:** Replace with Pydantic `BaseModel` in `schemas/`. (Phase 1.)

**Status:** OPEN — Phase 1

---

### TD-007: HTML-only context collection

**Severity:** HIGH
**File:** `src/utils/browser.py` — `fetch_page_context()`

**Description:**
Page context for generation and healing is HTML stripped by BeautifulSoup. Playwright can provide accessibility tree, console errors, network failures, and locator candidates — none of which are collected.

**Impact:**

- LLM lacks structured locator hints (a11y roles, aria-labels)
- Console errors during page load not captured
- Network failures not included in evidence
- Locator drift diagnosis limited to HTML structural matching

**Recommended Fix:** Build unified `src/context/` collector that captures all context types. (Phase 6.)

**Status:** OPEN — Phase 6

---

### TD-008: Module-level LLM singleton

**Severity:** HIGH
**File:** `src/utils/llm.py`

**Description:**
The line `client = OpenAI(base_url=base_url, api_key=api_key)` runs at import time. Any module that imports from `src/utils/llm` triggers client initialization, including test collection.

**Impact:**

- Unit tests require module-level patching or live network connection
- Cannot run tests in CI without LLM credentials
- Cannot swap providers between calls
- Prints to stdout on import

**Recommended Fix:** Replace with `LLMClientFactory.create(config)` pattern. No module-level side effects. (Phase 2.)

**Status:** OPEN — Phase 2

---

## MEDIUM

### TD-009: No retry or fallback policy

**Severity:** MEDIUM
**File:** `src/utils/llm.py`

**Description:**
Single LLM call with no retry. Transient failures (rate limits, connection errors, empty responses) return error strings that propagate through the pipeline as successful values.

**Impact:** Transient failures cause full healing sessions to fail. No differentiation between transient and permanent failures.

**Recommended Fix:** Configurable retry with exponential backoff. Fallback to secondary model on primary failure. (Phase 2.)

**Status:** OPEN — Phase 2

---

### TD-010: No model registry or capability metadata

**Severity:** MEDIUM
**File:** `src/utils/llm.py`

**Description:**
Model names are environment variable strings. No registry maps models to capabilities (vision support, context window, cost per token). Provider selection is a `if LLM_PROVIDER == "ollama"` branch.

**Impact:**

- Cannot route to vision model automatically based on capability
- Cannot enforce that a model supports structured output before calling it
- Adding new providers requires code changes

**Recommended Fix:** Model registry with capability metadata. LiteLLM routing. (Phase 2.)

**Status:** OPEN — Phase 2

---

### TD-011: No prompt versioning

**Severity:** MEDIUM
**Files:** `prompts/generator.md`, `prompts/healer.md`, `prompts/vision.md`

**Description:**
Prompts are loaded by name. No version field, no content hash, no audit trail linking a healing artifact to the prompt version that produced it.

**Impact:**

- Cannot A/B test prompts
- Cannot reproduce a past result with confidence
- Cannot detect silent prompt drift

**Recommended Fix:** Add `prompts/manifest.json` with name→version→hash mapping. Record prompt hash in all artifacts. (Phase 9.)

**Status:** OPEN — Phase 9

---

### TD-012: Evidence staleness in healer

**Severity:** MEDIUM
**File:** `src/agents/healer.py` — `gather_evidence()`

**Description:**
`gather_evidence()` fetches live DOM via `fetch_page_context()` during healing. The page state may have changed since the test failed. This is especially problematic for dynamic pages.

**Impact:**

- Healer receives DOM evidence that does not match the state at failure time
- Locator drift may be incorrectly diagnosed if the page has since been updated

**Recommended Fix:** Capture DOM snapshot during test execution (via Playwright trace or `page.content()` call on failure). Use the captured snapshot in evidence. (Phase 6.)

**Status:** OPEN — Phase 6

---

## LOW

### TD-013: `sanitize_for_shell()` dead code

**Severity:** LOW
**File:** `src/utils/validation.py`

**Description:**
`sanitize_for_shell()` is defined and has unit tests but is never called in any production code path. All subprocess calls use list arguments, making shell injection impossible and this function irrelevant.

**Impact:** Dead code increases maintenance surface; tests for it waste CI time.

**Recommended Fix:** Delete function and its unit tests.

**Status:** OPEN — Phase 3 cleanup

---

### TD-014: Vision agent logic duplicated in app.py

**Severity:** LOW
**Files:** `src/agents/vision.py`, `src/app.py`

**Description:**
`safe_analyze_visual()` in `app.py` (160 lines) reimplements screenshot capture, encoding, and vision LLM call. `vision.py` implements the same in `analyze_visual_ui()`. The app never calls the agent.

**Impact:** Two implementations of the same feature; bug fixes must be applied in two places.

**Recommended Fix:** Resolved by Phase 3 service layer extraction.

**Status:** OPEN — Phase 3

---

### TD-015: `TestRunResult` mock class

**Severity:** LOW
**File:** `src/agents/healer.py`

**Description:**
The `TestRunResult` class is a hand-rolled mock of `subprocess.CompletedProcess` used when Playwright times out or is not found.

**Impact:** Unnecessary complexity; inconsistent type with `subprocess.run()` return value.

**Recommended Fix:** Replace with a `RunResult` Pydantic model in `schemas/shared.py` and use it consistently for both subprocess results and error fallbacks.

**Status:** OPEN — Phase 1

---

## Resolved

None yet — audit complete, remediation starting.
