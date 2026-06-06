# Scoring

> How evaluation results are computed and interpreted.

---

## EvaluationResult

Every benchmark case produces an `EvaluationResult`:

```python
class EvaluationResult(BaseModel):
    example_id: str          # "heal-001"
    passed: bool             # True only when ALL checks pass
    score: float             # fraction of checks passed (0.0–1.0)
    duration_ms: int         # wall-clock time for this case
    details: dict            # per-check breakdown
    error: Optional[str]     # set if the runner raised an exception
```

### `passed` vs `score`

`passed` is strict: True only when every check passes. A case that passes 4 out of 5 checks has `passed=False` but `score=0.8`.

`score` is useful for tracking gradual improvement across prompt changes. `passed` is useful for regression detection — a previously-passing case that now fails.

---

## Check Types

### Classification Accuracy (`evaluate_classification`)

Single check: does `classified_type == case.checks.expected_failure_type`?

If `expected_failure_type` is `null` in the dataset, the check always passes (classification is not under test for that case).

Score: 1.0 (pass) or 0.0 (fail).

### Repair Quality (`evaluate_repair`)

Up to four checks:

| Check | When active | What is tested |
| --- | --- | --- |
| `classification` | `expected_failure_type` is set | classified_type == expected |
| `code-modified` | `code_must_change: true` | repaired_code != original_code |
| `fixed(pattern)` | `must_fix_pattern` is set | pattern NOT in repaired_code |
| `contains(pattern)` | `fixed_code_must_contain` is non-empty | each pattern IN repaired_code |

Score = `checks_passed / (checks_passed + checks_failed)`.

Example: a case with 4 checks where 3 pass has `score=0.75`, `passed=False`.

---

## Aggregate Metrics

`BenchmarkRun` computes:

| Metric | Formula | Interpretation |
| --- | --- | --- |
| `pass_rate` | `passed / total` | Fraction of cases that fully pass. Use for regression detection. |
| `mean_score` | `sum(scores) / total` | Average partial-credit score. Use for tracking improvement trends. |
| `mean_duration_ms` | `sum(durations) / total` | Average time per case. Use for latency tracking. |

---

## Interpreting Results

**100% pass_rate, mean_score=1.0:** All checks pass on all cases. The classifier or healer is working correctly for the current dataset.

**pass_rate < 100%, mean_score close to 1.0:** Some cases fail on a single check. Inspect `details.checks_failed` to find which check. Often a dataset case that needs updating or a minor prompt change.

**pass_rate drops between runs:** A regression. Compare `config.prompt_hash` between runs — if different, the prompt changed. If same, the model or provider changed.

**mean_duration_ms increases:** The LLM is slower (load, model size, retry count). Check `details.confidence` and `TraceMetadata.retry_count` in traces.

---

## Confidence Score (Healing-Specific)

The heuristic classifier returns a `confidence` value (0.0–1.0) alongside the failure type. This is recorded in `EvaluationResult.details`:

```json
{
  "classified_type": "TIMEOUT",
  "expected_type": "TIMEOUT",
  "confidence": 1.0,
  "reason": "TimeoutError pattern matched",
  "mode": "classification-only"
}
```

Confidence is not a pass/fail check — it is informational. A low confidence (< 0.7) means the heuristic was uncertain and the LLM fallback was more important. Use this to identify cases where the heuristic needs a new pattern.

---

## What the Scores Do Not Measure

**Test execution success.** The benchmark only runs lexical checks — it does not execute the repaired test against a live browser. A repair that passes all lexical checks may still fail at runtime if the fixed selector does not exist on the target page.

**LLM reasoning quality.** The benchmark does not evaluate the quality of `reasoning_steps` or `confidence_rationale`. It only checks whether the output code meets the repair criteria.

**Generation runtime correctness.** The generation benchmark checks code structure, not whether the generated test would pass when run. Use `run_test_streaming()` to verify a generated spec at runtime.
