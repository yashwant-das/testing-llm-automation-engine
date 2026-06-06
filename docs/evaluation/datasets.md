# Dataset Format

> How benchmark datasets are structured and extended.

---

## Overview

Datasets are JSON files versioned alongside the code. They encode labeled examples — inputs and expected outputs — that the benchmark runners use to measure quality.

Each dataset type has a fixed schema enforced by Pydantic models in `benchmarks/*/runner.py`.

---

## Healing Dataset (`repair_scenarios.json`)

**Location:** `benchmarks/healing/fixtures/repair_scenarios.json`

```json
{
  "version": "1.0.0",
  "description": "Human-readable description",
  "cases": [
    {
      "id": "heal-001",
      "description": "Short label for this case",
      "broken_test_file": "tests/fixtures/broken_selector.spec.ts",
      "injected_failure_type": "LOCATOR_NOT_FOUND",
      "error_log": "Error: locator('#submit-btn') could not be found on the page.",
      "checks": {
        "expected_failure_type": "LOCATOR_NOT_FOUND",
        "must_fix_pattern": "locator('#submit-btn')",
        "fixed_code_must_contain": ["data-testid"],
        "code_must_change": true
      }
    }
  ]
}
```

### Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `id` | string | Unique case identifier (`heal-NNN`) |
| `description` | string | Human-readable label |
| `broken_test_file` | string | Path relative to project root |
| `injected_failure_type` | string | The `FailureType` enum value that was introduced |
| `error_log` | string | Synthetic error log the broken test would produce |
| `checks.expected_failure_type` | string or null | Expected heuristic classification result |
| `checks.must_fix_pattern` | string or null | String that must NOT appear in repaired code |
| `checks.fixed_code_must_contain` | string[] | Strings that MUST appear in repaired code |
| `checks.code_must_change` | bool | Whether any code change is required |

### Valid `FailureType` values

`LOCATOR_NOT_FOUND`, `LOCATOR_DRIFT`, `TIMEOUT`, `JAVASCRIPT_ERROR`, `ASSERTION_FAILED`, `ENVIRONMENT_ISSUE`, `POTENTIAL_APP_DEFECT`, `UNKNOWN`

---

## Generation Dataset (`web_scenarios.json`)

**Location:** `benchmarks/generation/fixtures/web_scenarios.json`

```json
{
  "version": "1.0.0",
  "description": "...",
  "scenarios": [
    {
      "id": "gen-001",
      "description": "Login form with success message verification",
      "url": "https://the-internet.herokuapp.com/login",
      "feature_description": "Login with tomsmith and SuperSecretPassword!. Verify success message.",
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

---

## Mutation Engine

The `benchmarks/mutations/mutator.py` module creates broken specs from working ones. Use it to generate healing dataset cases without writing broken code by hand.

```python
from benchmarks.mutations.mutator import mutate, MutationType

broken_code = mutate(working_code, MutationType.SELECTOR_DRIFT, seed=42)
# broken_code now has a selector that does not exist in the DOM
```

Mutation types and the failure type they produce:

| MutationType | What changes | Produces |
| --- | --- | --- |
| `SELECTOR_DRIFT` | Replaces a valid locator with `#nonexistent-id-xyz` | `LOCATOR_NOT_FOUND` |
| `TIMEOUT_REDUCTION` | Changes `{ timeout: N }` to `{ timeout: 1 }` | `TIMEOUT` |
| `IMPORT_REMOVAL` | Removes `import { test, expect }` | `JAVASCRIPT_ERROR` |
| `ASSERTION_SWAP` | Changes `toHaveText` to `toBe` | `ASSERTION_FAILED` |

The `seed` parameter makes mutations deterministic — same seed + same input always produces the same broken code.

---

## Dataset Versioning

The `version` field in each dataset file must be incremented when cases are added, modified, or removed. This version is recorded in every `BenchmarkRunConfig` under `dataset_version`, linking the run record to the exact dataset that produced it.

Never modify an existing case without incrementing the dataset version. Cross-run comparison requires stable case IDs.

---

## Adding a Healing Case

1. Create or identify a broken fixture file in `tests/fixtures/`
2. Run the fixture with `npx playwright test <file>` to capture the real error log
3. Add the case to `repair_scenarios.json` with the actual error log text
4. Set `checks.expected_failure_type` to the failure type the heuristic should return
5. Increment `version` in the dataset JSON
6. Run the benchmark to verify the new case passes classification
