# Adding a New Benchmark

> How to extend the evaluation framework with a new dataset or runner.

---

## Adding a Healing Case

The fastest path. No code changes required.

1. **Create a broken fixture** in `tests/fixtures/`:

```typescript
// tests/fixtures/broken_role.spec.ts
import { test, expect } from '@playwright/test';

test('Submit form', async ({ page }) => {
  await page.goto('https://example.com/form');
  // BUG: wrong role name
  await page.getByRole('button', { name: 'Send' }).click(); // should be "Submit"
  await expect(page.locator('.success')).toBeVisible();
});
```

1. **Capture the real error log** by running the test:

```bash
npx playwright test tests/fixtures/broken_role.spec.ts 2>&1 | tail -20
```

1. **Add the case** to `benchmarks/healing/fixtures/repair_scenarios.json`:

```json
{
  "id": "heal-005",
  "description": "Wrong getByRole name — button name drifted from 'Send' to 'Submit'",
  "broken_test_file": "tests/fixtures/broken_role.spec.ts",
  "injected_failure_type": "ASSERTION_FAILED",
  "error_log": "Error: locator.click: Error: strict mode violation...",
  "checks": {
    "expected_failure_type": "ASSERTION_FAILED",
    "must_fix_pattern": "name: \"Send\"",
    "fixed_code_must_contain": ["name: \"Submit\""],
    "code_must_change": true
  }
}
```

1. **Increment** `version` in `repair_scenarios.json`

1. **Run the benchmark** to verify:

```bash
uv run python -c "
from benchmarks.healing.runner import run_healing_benchmark, load_dataset
from schemas.evaluation import BenchmarkRunConfig
from pathlib import Path
config = BenchmarkRunConfig(
    model='heuristic', provider='local',
    prompt_name='n/a', prompt_version='1', prompt_hash='n/a',
    temperature=0.0, dataset_version='1.1.0', benchmark_type='healing-classification',
)
run = run_healing_benchmark(Path('benchmarks/healing/fixtures/repair_scenarios.json'), Path('.'), config)
print(f'{run.passed}/{run.total} passed')
for r in run.results:
    print(f'  {r.example_id}: {\"PASS\" if r.passed else \"FAIL\"} — {r.details}')
"
```

---

## Adding a Generation Scenario

1. **Add the scenario** to `benchmarks/generation/fixtures/web_scenarios.json`:

```json
{
  "id": "gen-006",
  "description": "Checkout flow with product add and payment",
  "url": "https://example-shop.com/checkout",
  "feature_description": "Add a product to cart and complete checkout with test card.",
  "checks": {
    "must_import": ["@playwright/test"],
    "must_use_assertions": ["expect"],
    "must_not_use_deprecated": ["waitForSelector"],
    "must_contain_url": true,
    "preferred_locators": ["getByRole", "getByLabel"]
  }
}
```

1. Increment `version` in the dataset JSON

1. Run the generation benchmark (requires live LLM):

```python
from benchmarks.generation.runner import run_generation_benchmark
from src.agents.generator import generate_test_script

def generator_fn(url, story):
    return generate_test_script(url, story).code

run = run_generation_benchmark(dataset_path, config, generator_fn=generator_fn)
```

---

## Adding a New Benchmark Type

For a completely new benchmark (e.g., "context collection quality"):

1. **Create the dataset schema** — add a Pydantic model in the new runner file:

```python
class ContextCase(BaseModel):
    id: str
    url: str
    expected_element_count: int
    expected_a11y_role: str
```

1. **Create the runner** in `benchmarks/<new_type>/runner.py`:

```python
from schemas.evaluation import BenchmarkRun, BenchmarkRunConfig, EvaluationResult

def evaluate_context(case: ContextCase, snapshot: ContextSnapshot) -> EvaluationResult:
    """Pure function — no I/O."""
    checks_passed = []
    checks_failed = []
    # ... lexical checks ...
    return EvaluationResult(
        example_id=case.id,
        passed=len(checks_failed) == 0,
        score=len(checks_passed) / (len(checks_passed) + len(checks_failed)),
        details={"checks_passed": checks_passed, "checks_failed": checks_failed},
    )

def run_context_benchmark(dataset_path: Path, config: BenchmarkRunConfig, ...) -> BenchmarkRun:
    ...
```

1. **Create a dataset fixture** in `benchmarks/<new_type>/fixtures/`

1. **Add `__init__.py`** files for the new package

1. **Write unit tests** in `tests/unit_test_<new_type>.py`

---

## Key Rules

- Evaluator functions must be **pure** — no file writes, no network calls, no LLM calls
- Runners may read files (datasets, fixture specs) but must not write files unless explicitly saving a report
- Every new benchmark type must have unit tests that run without a live LLM or browser
- Dataset files must include a `version` field that changes when cases are added or modified
