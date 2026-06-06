# Benchmark Dataset Format

> Phase 7 — Evaluation Framework
> All datasets are JSON files versioned alongside the code.

---

## Generation Dataset (`web_scenarios.json`)

Each scenario exercises the generator on a real URL + user story.
Checks are **lexical** — they inspect the generated TypeScript for structural
quality without running the code.

```json
{
  "version": "1.0.0",
  "description": "Human-readable description of this dataset.",
  "scenarios": [
    {
      "id": "gen-NNN",
      "description": "Short label for the scenario.",
      "url": "https://target-url.example.com/path",
      "feature_description": "User story in plain English.",
      "checks": {
        "must_import": ["@playwright/test"],
        "must_use_assertions": ["expect"],
        "must_not_use_deprecated": ["waitForSelector"],
        "must_contain_url": true,
        "preferred_locators": ["getByRole", "getByLabel"]
      }
    }
  ]
}
```

### Check fields

| Field | Type | Description |
| --- | --- | --- |
| `must_import` | `string[]` | Substrings that must appear in the code (e.g. `"@playwright/test"`). |
| `must_use_assertions` | `string[]` | Assertion helpers that must appear (e.g. `"expect"`). |
| `must_not_use_deprecated` | `string[]` | Deprecated APIs that must NOT appear. |
| `must_contain_url` | `boolean` | Whether the scenario URL must appear verbatim. |
| `preferred_locators` | `string[]` | Modern locator APIs that boost score (not a hard gate). |

---

## Healing Dataset (`repair_scenarios.json`)

Each case references a **broken fixture file** and provides a synthetic error
log that the healer would see in production.  Two evaluation modes:

- **Classification-only** (no `healer_fn`): checks whether
  `classify_failure_heuristic(error_log)` returns the expected failure type.
- **Full repair** (with `healer_fn`): additionally checks the repaired code
  against `checks.must_fix_pattern` and `checks.fixed_code_must_contain`.

```json
{
  "version": "1.0.0",
  "description": "Human-readable description.",
  "cases": [
    {
      "id": "heal-NNN",
      "description": "Short label.",
      "broken_test_file": "tests/fixtures/broken_selector.spec.ts",
      "injected_failure_type": "LOCATOR_NOT_FOUND",
      "error_log": "Synthetic error log that triggers the right heuristic.",
      "checks": {
        "expected_failure_type": "LOCATOR_NOT_FOUND",
        "must_fix_pattern": "locator('#old-id')",
        "fixed_code_must_contain": ["data-testid"],
        "code_must_change": true
      }
    }
  ]
}
```

### Check fields

| Field | Type | Description |
| --- | --- | --- |
| `expected_failure_type` | `string` | The `FailureType` enum value the heuristic should return. |
| `must_fix_pattern` | `string\|null` | Pattern that must **not** appear in the repaired code. |
| `fixed_code_must_contain` | `string[]` | Patterns that must appear in the repaired code. |
| `code_must_change` | `boolean` | Whether the repair must produce any change at all. |

### Supported FailureType values

| Value | When |
| --- | --- |
| `LOCATOR_NOT_FOUND` | Locator resolved to 0 elements (no suggestion) |
| `LOCATOR_DRIFT` | Locator matched 0 elements with Playwright suggestion, or strict-mode violation |
| `TIMEOUT` | TimeoutError, `waiting for selector/locator`, execution timeout |
| `ASSERTION_FAILED` | `expect(received).toBe(expected)` pattern |
| `JAVASCRIPT_ERROR` | ReferenceError or TypeError in logs |
| `ENVIRONMENT_ISSUE` | TargetClosedError or browser crash |
| `POTENTIAL_APP_DEFECT` | HTTP 404/500 or `net::ERR_ABORTED` |
| `UNKNOWN` | No pattern matched |

---

## Reproducibility Requirements

Every benchmark run records:

- `model` + `model_version` — exact model identifier
- `prompt_name` + `prompt_hash` — 16-char SHA-256 prefix of the prompt content
- `temperature` — must be `0.0` for reproducible runs
- `seed` — optional integer seed (provider-dependent)
- `dataset_version` — semver string matching the dataset file's `version` field
- `timestamp` — ISO-8601 run start time

Reports are written to `benchmarks/reports/` as timestamped JSON files.
Use `BenchmarkRun.save_report(path)` to write them.

---

## Adding a New Scenario or Case

1. Add the entry to the appropriate JSON file.
2. Increment the `version` field (semver patch bump for additions).
3. Run the benchmark to confirm the new entry passes or fails as expected.
4. Commit both the dataset change and the baseline report together.
