# Architecture Review

> Phase 0 — Complete Repository Audit
> Audited: 2026-06-06
> Auditor: Principal Engineer (Claude)

---

## 1. Repository Overview

**Purpose:** LLM-powered Playwright test generation and self-healing engine.
**Stack:** Python 3.10+, Gradio 6.2, OpenAI SDK 2.14, Playwright 1.57, BeautifulSoup4.
**Size:** ~1,800 LOC Python, ~300 LOC TypeScript (tests), 3 prompt files.
**Test Coverage:** 4 unit test files; no integration tests; no benchmark framework.

---

## 2. Current Architecture Map

```text
src/
├── app.py              # Gradio UI — 876 lines — owns orchestration (PROBLEM)
├── agents/
│   ├── generator.py    # DOM → LLM → .spec.ts
│   ├── healer.py       # Run → Evidence → LLM → Patch → Verify
│   └── vision.py       # Screenshot → Vision LLM → .spec.ts
├── models/
│   └── healing_model.py # @dataclass models (not Pydantic)
└── utils/
    ├── llm.py           # OpenAI client + regex parsers
    ├── browser.py       # Playwright HTML extractor
    ├── validation.py    # Input sanitization
    ├── formatting.py    # ANSI stripping, output formatting
    └── prompt_loader.py # Reads prompts/*.md

prompts/
├── generator.md         # System prompt (no versioning)
├── healer.md            # System prompt with {format} injection
└── vision.md            # System prompt

tests/
├── unit_test_classification.py
├── unit_test_fixer.py
├── unit_test_json.py
└── unit_test_validation.py
```

---

## 3. Strengths

| Strength | Detail |
| --- | --- |
| Externalized prompts | Prompts live in `prompts/*.md`, not buried in code |
| Hybrid heuristics | `classify_failure_heuristic()` handles high-confidence patterns deterministically before calling the LLM |
| Structured artifact output | `HealingDecision` and `ExecutionTimeline` are serialized to JSON for every run |
| Bounded execution | Max retries is configurable; no infinite loops |
| Input validation | URL, file path, and description validated before processing |
| Unit tests exist | Core heuristic, JSON extraction, fix application, and validation are tested |
| Fuzzy indentation matching | `apply_fix()` handles LLM whitespace drift with sliding window fallback |

---

## 4. Weaknesses

| Weakness | Severity | Impact |
| --- | --- | --- |
| UI owns orchestration | CRITICAL | `app.py` duplicates the entire healing loop; healer agent's `attempt_healing()` is bypassed |
| String-based LLM output parsing | HIGH | `extract_json_block()` uses brace-slicing fallback; zero schema enforcement |
| No structured outputs | HIGH | LLM returns freeform JSON; any field rename breaks silently |
| Dataclasses instead of Pydantic | HIGH | No field validation, no schema export, no retry-on-parse-failure |
| No evaluation framework | HIGH | No way to measure if a model or prompt change improved results |
| No observability | HIGH | No trace IDs, no token tracking, no latency metrics |
| String replacement healing | HIGH | `apply_fix()` is fragile text surgery; no AST awareness |
| HTML-only context collection | MEDIUM | No accessibility tree, no console errors, no network failures, no Playwright locator hints |
| Module-level LLM singleton | MEDIUM | `client = OpenAI(...)` runs at import time; breaks tests without mocking |
| No retry/fallback policy | MEDIUM | Single LLM call; transient failures return error strings |
| No model registry | MEDIUM | Model names are env-var strings; no capability metadata, no routing |
| Prompt versioning absent | MEDIUM | No way to A/B test prompts or know which version produced a result |
| Vision logic duplicated in app.py | LOW | `safe_analyze_visual()` is 100 lines that reimplement `vision.py` |
| Generator logic duplicated in app.py | LOW | `safe_generate_test()` and `safe_run_test()` duplicate `generator.py` logic |
| `sanitize_for_shell()` dead code | LOW | Defined and tested but never called in production paths |

---

## 5. Technical Debt Inventory

See `technical-debt.md` for the full register. Summary:

- **3 CRITICAL** items (UI orchestration, LLM parsing, no structured outputs)
- **5 HIGH** items (evaluation, observability, AST healing, context collection, dataclasses)
- **4 MEDIUM** items (singleton client, retry policy, model registry, prompt versioning)
- **3 LOW** items (dead code, duplication, vision agent duplication)

---

## 6. AI Layer Analysis

### LLM Client (`src/utils/llm.py`)

```python
# Current: module-level singleton initialized at import time
client = OpenAI(base_url=base_url, api_key=api_key)
```

**Problems:**

- Initialization side-effect at import time makes unit testing require patching
- No retry logic on transient failures
- No timeout configuration beyond the default
- Provider selection is a string comparison (`if LLM_PROVIDER == "ollama"`)
- No fallback chain (if primary fails, no backup)

### Response Parsing

Two fragile parsers:

**`extract_code_block()`** — regex with fallback string cleanup:

```python
pattern = r"```(?:typescript|ts|javascript|js)?\n(.*?)```"
# Falls back to: strip prefix lines starting with "here", "sure", "certainly"
```

**`extract_json_block()`** — regex with brace-slicing fallback:

```python
start = llm_response.find("{")
end = llm_response.rfind("}")
json_str = llm_response[start : end + 1]
```

Both are fragile. Neither validates the extracted content against a schema.

### Prompt Engineering

- Healer prompt uses Python `.format()` injection for heuristic context — works but not type-safe
- No prompt versioning
- Generator prompt is 3 lines; healer prompt is ~40 lines with embedded JSON schema
- The JSON schema in `healer.md` and the `HealingDecision` dataclass are not linked — drift is invisible

---

## 7. Generation Pipeline Analysis

```text
URL + Story
    → validate_and_sanitize_url()
    → fetch_page_context()          # Playwright → BS4 HTML strip → 30,000 chars
    → load_prompt("generator")
    → client.chat.completions.create()
    → extract_code_block()          # FRAGILE
    → write to tests/generated/
    → subprocess("npx playwright test")
```

**Missing:**

- Structured output enforcement (model should return typed JSON, not raw code)
- Accessibility tree context
- Network/console error capture during page fetch
- Locator candidate hints from Playwright

---

## 8. Healing Pipeline Analysis

```text
.spec.ts path
    → run_test()                    # subprocess → Playwright
    → gather_evidence()             # logs + screenshot glob + HTML fetch
    → classify_failure_heuristic()  # deterministic regex classification
    → analyze_and_plan()            # LLM call → extract_json_block() → json.loads()
    → apply_fix()                   # string replace with sliding window fallback
    → run_test()                    # verify
    → emit_artifacts()              # JSON files
```

**Critical Issues:**

- `apply_fix()` is string surgery. If the LLM proposes a structural change (add import, reorganize test body), it fails silently.
- `gather_evidence()` fetches the live DOM on every attempt, not the DOM at failure time — evidence may be stale.
- `analyze_and_plan()` parses `json.loads(extract_json_block(raw))` — two points of failure with no retry.
- Screenshot evidence is found via `glob("**/*.png")` on the most recently modified file — fragile; picks up unrelated screenshots.

---

## 9. UI Layer Analysis (`src/app.py` — 876 lines)

This is the most structurally damaging file in the repository.

**What it should do:** Accept inputs, call services, display results.
**What it actually does:** Reimplements the entire generation and healing pipelines inline.

Specific violations:

- `safe_generate_test()` (97 lines): duplicates all of `generator.py`'s generation logic
- `safe_run_test()` (104 lines): duplicates all of `generator.py`'s run logic
- `safe_analyze_visual()` (160 lines): duplicates all of `vision.py`'s analysis logic
- `wrap_healer()` (260 lines): reimplements the healing loop from `healer.attempt_healing()`, importing healer internals (`analyze_and_plan`, `apply_fix`, `gather_evidence`, `run_test`, `emit_artifacts`)

The agents (`generator.py`, `vision.py`) exist but are unused by the UI. The UI goes around them.

---

## 10. Data Model Analysis (`src/models/healing_model.py`)

Uses Python `@dataclass`:

```python
@dataclass
class HealingDecision:
    test_file: str
    failure_type: FailureType
    confidence_score: float
    ...
```

**Missing:**

- Pydantic validation (field constraints, range checks, coercion)
- Schema export for structured output enforcement
- No `GenerationResult` model — generator returns raw strings
- No `ContextSnapshot` model — browser context is raw HTML strings
- No `EvaluationResult` model — no evaluation framework exists

---

## 11. Current State vs Target State

| Area | Current State | Target State |
| --- | --- | --- |
| LLM Output | Regex + brace-slice parsing | Pydantic structured outputs with retry |
| Healing Logic | String replacement + sliding window | AST-based transformations |
| Healing Repair | No failure taxonomy beyond FailureType enum | Deterministic repair rules per failure class |
| Evaluation | 4 unit tests | Benchmark framework with datasets and model comparison |
| Observability | JSON artifacts | OpenTelemetry traces + Langfuse metrics |
| LLM Routing | Direct `OpenAI()` calls | LiteLLM router with fallback policies |
| Context Collection | HTML only (BeautifulSoup) | DOM + a11y tree + console + network + locator candidates |
| Data Models | Python `@dataclass` | Pydantic `BaseModel` with validation |
| Prompt Management | Unversioned markdown files | Versioned prompts with A/B capability |
| UI Architecture | UI owns orchestration | UI calls services; services call agents |
| Architecture | Generator/Vision/Healer monolithic agents | Decomposed: runner, evidence, classifier, planner, repair, verifier |
| Explainability | HealingDecision JSON artifact | Full reasoning chain, confidence rationale, model metadata, prompt version |
| Reproducibility | None | Seed + model version + prompt version recorded per run |
| Testing | Unit tests (no isolation) | Isolated unit tests + benchmark datasets + integration harness |

---

## 12. REMOVE\_IMMEDIATELY

### 12.1 Logic Duplication in `src/app.py`

**Why it exists:** The UI was built first and the agent modules were extracted later (or the agents were never wired back in).

**Why it is obsolete:** `generator.py`, `vision.py`, and `healer.py` exist and should be the canonical implementation.

**Risk of removal:** ZERO — the agents already implement the same logic correctly.

**Recommended replacement:** UI calls `generate_test_script()`, `run_generated_test()`, `analyze_visual_ui()`, and `attempt_healing()` from the agent modules. Stream progress via callbacks or queues.

Specific functions to delete from `app.py`:

- `safe_generate_test()` — replace with call to `generator.generate_test_script()`
- `safe_run_test()` — replace with call to `generator.run_generated_test()`
- `safe_analyze_visual()` — replace with call to `vision.analyze_visual_ui()`
- The inline healing loop in `wrap_healer()` — replace with call to `healer.attempt_healing()`

### 12.2 `sanitize_for_shell()` in `src/utils/validation.py`

**Why it exists:** Defensive measure written early in development.

**Why it is obsolete:** Never called in any production path. All subprocess calls use list arguments (not shell strings), making shell injection impossible. Shell sanitization is irrelevant.

**Risk of removal:** ZERO — deleting dead code.

**Recommended replacement:** None. Delete function and its tests.

### 12.3 `TestRunResult` mock class in `src/agents/healer.py`

**Why it exists:** Mimics `subprocess.CompletedProcess` for error fallback cases.

**Why it is obsolete:** `subprocess.CompletedProcess` can be constructed directly; or a proper `RunResult` dataclass/Pydantic model should replace it.

**Risk of removal:** LOW — requires updating the two fallback return sites.

**Recommended replacement:** Proper `RunResult` Pydantic model in `schemas/`.

### 12.4 Module-level client initialization in `src/utils/llm.py`

**Why it exists:** Convenience — "initialize once at startup."

**Why it is obsolete:** Makes unit testing impossible without module-level patching; prevents dynamic reconfiguration; leaks stderr output on import.

**Risk of removal:** LOW — requires updating callers to use an injected or factory-constructed client.

**Recommended replacement:** `LLMClient` class or factory function; dependency injection pattern.

---

## 13. Modernization Opportunities

| Opportunity | Value | Effort |
| --- | --- | --- |
| Pydantic structured outputs | Eliminates fragile parsing, adds schema enforcement | Medium |
| LiteLLM router | Provider abstraction, retry, fallback, local LLM routing | Medium |
| AST-based repair (ts-morph) | Structural fixes, import management, rename-safe | High |
| OpenTelemetry tracing | Token usage, latency, retry count per run | Medium |
| Benchmark framework | Reproducible model/prompt comparison | High |
| Unified context collector | Richer inputs for generation and healing | Medium |
| Service layer extraction | UI → Services → Agents; removes orchestration from UI | Low-Medium |
| Prompt versioning | A/B testing, reproducibility, audit trail | Low |

---

## 14. Severity Summary

| Severity | Count | Items |
| --- | --- | --- |
| CRITICAL | 3 | UI orchestration ownership, no structured outputs, string-based repair |
| HIGH | 5 | No evaluation, no observability, dataclass models, HTML-only context, module singleton |
| MEDIUM | 4 | No retry/fallback, no model registry, no prompt versioning, evidence staleness |
| LOW | 3 | Dead code (sanitize\_for\_shell), generator/vision duplication, TestRunResult mock |
