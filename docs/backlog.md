# Backlog

> Potential future work, research topics, and experiments.
> Items here are NOT scheduled — each requires a decision before becoming planned work.
> Last updated: 2026-06-06 (Phase 12 — prerequisites updated: all Modernization Program phases now complete)

---

## Research Topics

### R-001: Mutation testing for generated tests

Introduce deliberate mutations to generated tests (wrong selector, wrong assertion value, wrong URL)
to create a labeled dataset for the healing benchmark. Measure what percentage of each mutation
class is correctly diagnosed and repaired.

**Value:** Gold-standard healing benchmark with known ground truth. More rigorous than the current
synthetic error-log approach.

---

### R-002: Playwright trace artifact integration

Playwright generates `.zip` trace files containing DOM snapshots, screenshots, and network logs
at each step. Integrating trace parsing into evidence collection would provide deterministic,
point-in-time DOM snapshots rather than re-fetching live pages.

**Value:** Eliminates evidence staleness; richer evidence for complex failures.

---

### R-003: LLM-as-judge for generation quality

Use a separate LLM call to score generated tests on: selector quality, test completeness,
and code style. Use scores to drive prompt improvement.

**Value:** Automated quality gate for generated tests; removes human review bottleneck.

---

### R-004: Selector stability scoring

Implement a heuristic that scores each generated selector on stability
(data-test-id > aria-label > role > CSS class > XPath).
Warn or reject tests that rely on unstable selectors.

**Value:** Prevents fragile tests from entering the test suite.

---

### R-005: Parallel healing attempts

For complex failures where the root cause is ambiguous, run multiple repair strategies
in parallel and take the first one that produces a passing test.

**Value:** Higher healing success rate on ambiguous failures.

---

### R-006: Multi-step test generation

Current generator produces single-test files. Investigate generating full test suites from
a user story document or a sitemap.

**Value:** More realistic test coverage from a single generation run.

---

## Feature Ideas

### F-001: Prompt A/B testing harness

Given two prompt versions and a benchmark dataset, run both and produce a side-by-side
comparison of metrics (success rate, confidence score distribution, token usage).

**Value:** Systematic prompt improvement without manual evaluation.

---

### F-002: CLI interface

Add a proper CLI using `typer` or `click` so the system can be invoked without the Gradio UI.
Useful for CI integration and scripting.

**Effort:** Low. The service layer exists; the CLI would be thin wrappers around service functions.

---

### F-003: GitHub Actions integration

Provide a GitHub Actions workflow that runs the healer on failing tests in CI and commits
the repaired file with a `[auto-healed]` commit message.

**Value:** Demonstrates real-world integration value.

---

### F-004: Test intent validation

After generating a test, verify that it actually tests what the user story describes.
Use an LLM with a structured output schema to score intent coverage.

---

### F-005: Failure pattern library

Accumulate a library of known failure patterns (e.g., "modal blocking input", "lazy-loaded
element", "CAPTCHA") with deterministic repair rules. Extends `classify_failure_heuristic()`
to cover more cases without LLM involvement.

**Value:** Faster, cheaper, more reliable healing for common patterns.

---

### F-006: Healing confidence threshold

Add a minimum confidence threshold. If the LLM produces a fix with confidence below the
threshold, skip application and mark as "manual review required".

**Effort:** Low. The confidence score is already in `HealingDecision`.

---

## Experiments

### E-001: tree-sitter for failure log parsing

Use tree-sitter Python grammar to parse Playwright stack traces structurally
rather than with regex. May improve failure classification accuracy for complex nested errors.

---

### E-002: Vision-based locator extraction

Instead of using vision LLM to generate entire tests, use it only to extract locator candidates
from a screenshot (bounding boxes → element labels → suggested selectors). Feed these into the
DOM-based generator as hints.

---

### E-003: Embedding-based selector similarity

When a locator fails, use embeddings to find semantically similar selectors in the current DOM.
Potentially more robust than exact-string or regex matching.

---

### E-004: CodeBERT for test quality scoring

Fine-tune or prompt a code-specialized model to score Playwright test quality on established
best-practice dimensions (no magic waits, no `page.waitForTimeout`, proper assertions).

---

## Cleanup Work

Known rough edges that reduce maintainability but have no user-visible impact.

| Item | Notes |
| --- | --- |
| `src/utils/llm.py::extract_json_block()` | Private implementation used inside `parse_llm_response()` — not a candidate for removal. Exported in the module docstring as a convenience; could be made private (`_extract_json_block`) if desired. |
| `src/utils/llm.py::extract_code_block()` | Still called in `src/agents/generator.py`. Remove only after migrating the generator to use `GenerationResult.model_validate()` on the raw LLM output. |
