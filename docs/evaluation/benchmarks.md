# Benchmark Methodology

> How the evaluation framework measures quality changes.

---

## What Is a Benchmark?

A benchmark is a reproducible measurement. It takes a fixed set of labeled inputs, runs the system under test, and compares outputs against expected values. Two benchmark runs with the same configuration must produce the same results.

The evaluation framework has three benchmark types: **healing**, **generation**, and **intent validation**.

---

## Healing Benchmark

**File:** `benchmarks/healing/runner.py`
**Dataset:** `benchmarks/healing/fixtures/repair_scenarios.json`

Evaluates two capabilities:

1. **Classification accuracy** — does the heuristic classifier correctly identify the failure type from the error log?
2. **Repair quality** — does the healer produce code that fixes the problem? (requires live LLM)

### Classification-Only Mode (default)

Runs `classify_failure_heuristic(case.error_log)` for each case and checks the result against `case.checks.expected_failure_type`.

No LLM, no browser, no network. Deterministic. Completes in under 10ms.

```python
from benchmarks.healing.runner import run_healing_benchmark
from schemas.evaluation import BenchmarkRunConfig
from pathlib import Path

config = BenchmarkRunConfig(
    model="heuristic-classifier",
    provider="local",
    prompt_name="classify_failure_heuristic",
    prompt_version="1",
    prompt_hash="n/a",
    temperature=0.0,
    dataset_version="1.0.0",
    benchmark_type="healing-classification",
)
run = run_healing_benchmark(
    Path("benchmarks/healing/fixtures/repair_scenarios.json"),
    Path("."),
    config,
)
print(f"{run.passed}/{run.total} passed ({run.pass_rate*100:.0f}%)")
```

### Full Repair Mode (requires LLM)

Injects a `healer_fn` that calls the full pipeline:

```python
def healer_fn(broken_code: str, error_log: str) -> str:
    from src.healing.evidence import Evidence
    from src.healing.planner import analyze_and_plan
    from src.healing.repair import apply_fix
    evidence = Evidence(error_log=error_log)
    decision = analyze_and_plan("test.spec.ts", broken_code, evidence)
    return apply_fix("test.spec.ts", broken_code, decision)

run = run_healing_benchmark(dataset_path, project_root, config, healer_fn=healer_fn)
```

Full repair checks:

- Classification correct
- Code was modified
- Broken pattern (`must_fix_pattern`) no longer present
- Required patterns (`fixed_code_must_contain`) are present

---

## Generation Benchmark

**File:** `benchmarks/generation/runner.py`
**Dataset:** `benchmarks/generation/fixtures/web_scenarios.json`

Evaluates generated test quality with lexical checks:

| Check | What it verifies |
| --- | --- |
| `must_import` | Required import strings appear in the code |
| `must_use_assertions` | At least one `expect()` call |
| `must_not_use_deprecated` | `waitForSelector` absent |
| `must_contain_url` | Target URL referenced in the test |
| `preferred_locators` | `getByRole` or `getByLabel` used |

These are **lexical** checks — they inspect the text of the generated TypeScript without parsing or running it. Fast and dependency-free.

```python
from benchmarks.generation.runner import run_generation_benchmark

def generator_fn(url: str, feature_description: str) -> str:
    from src.agents.generator import generate_test_script
    result = generate_test_script(url, feature_description)
    return result.code

run = run_generation_benchmark(dataset_path, config, generator_fn=generator_fn)
```

---

## Intent Validation Benchmark

**File:** `benchmarks/intent_validation/runner.py`

Six universal quality checks applied to any generated test:

1. Imports `@playwright/test`
2. Has at least one `expect()` assertion
3. Does not use `waitForSelector()` (deprecated)
4. References the target URL
5. Uses `getByRole()` or `getByLabel()` (accessible locators)
6. Has a `test()` block

```python
from benchmarks.intent_validation.runner import run_intent_validation

cases = [IntentCase(url="https://example.com", generated_code=code)]
run = run_intent_validation(cases, config)
```

---

## EvaluationResult

Every evaluated case produces an `EvaluationResult`:

```python
class EvaluationResult(BaseModel):
    example_id: str          # "heal-001"
    passed: bool             # all checks passed
    score: float             # fraction of checks passed (0.0–1.0)
    duration_ms: int         # time for classification + repair
    details: dict            # check-level breakdown
    error: Optional[str]     # error message if runner raised
```

`details` contains `checks_passed`, `checks_failed`, `classified_type`, `expected_type`, and `confidence`. Use this to understand exactly which check failed and why.

---

## BenchmarkRun Aggregates

`BenchmarkRun` computes aggregate metrics from all results:

```python
run.total          # number of cases
run.passed         # cases where passed == True
run.failed         # cases where passed == False
run.pass_rate      # passed / total
run.mean_score     # mean of all EvaluationResult.score values
run.mean_duration_ms  # mean wall-clock time per case
```

Save and compare:

```python
path = run.save_report(Path("benchmarks/reports/"))
# → benchmarks/reports/healing-classification_heuristic-classifier_20260606_142311.json
```

---

## Running From the UI

The **Evaluation** tab runs the healing classification benchmark with one click. No configuration required. Results appear as a markdown table.

The Evaluation tab always runs in classification-only mode (no LLM required). Full repair mode must be run from Python.
