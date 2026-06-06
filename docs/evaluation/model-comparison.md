# Model Comparison

> How to run and compare models across benchmark runs.

---

## Workflow

To compare two models:

1. Configure LLM provider to Model A
2. Run benchmark with `temperature=0.0`, `seed=42`, record `prompt_hash`
3. Save report: `run.save_report(Path("benchmarks/reports/"))`
4. Configure LLM provider to Model B
5. Run benchmark with identical config
6. Save report
7. Compare the two JSON files

```bash
# Quick comparison
jq '{model: .config.model, passed: .passed, total: .total, mean_score: .mean_score}' \
  benchmarks/reports/run_modelA.json
jq '{model: .config.model, passed: .passed, total: .total, mean_score: .mean_score}' \
  benchmarks/reports/run_modelB.json
```

---

## Required Fields for Valid Comparison

Two runs are comparable only when:

| Field | Must be equal |
| --- | --- |
| `dataset_version` | Same dataset |
| `prompt_hash` | Same prompt content |
| `temperature` | Same (ideally 0.0) |
| `seed` | Same (ideally fixed) |
| `benchmark_type` | Same type |

Different `model` and `model_version` is expected — that is the point of the comparison.

---

## Classification-Only Comparison

The heuristic classifier is model-independent. Its benchmark result is always the same, regardless of which LLM is configured. Use classification-only runs to verify the benchmark framework itself, not to compare models.

Compare models on the **full repair** benchmark, which actually calls the LLM.

---

## What to Look For

**pass_rate improvement:** The primary signal. If Model B passes 4/4 cases vs Model A's 3/4, Model B is better for this dataset.

**mean_score improvement:** Secondary signal. A model that scores 0.95 average vs 0.80 is making more correct repairs even on the cases it does not fully pass.

**mean_duration_ms:** Cost/quality tradeoff. A model that passes 4/4 but takes 3x longer is not clearly better — it depends on the application's latency budget.

**Per-case regression:** A model that passes new cases but fails previously-passing cases is a regression for the failing cases. Inspect `details.checks_failed` on both runs for those case IDs.

---

## Prompt Comparison

To compare two prompt versions with the same model:

1. Edit `prompts/healer.md`
2. Increment `version` in `prompts/manifest.json`
3. Run benchmark — `prompt_version` and `prompt_hash` will differ from the previous run
4. Compare reports

The `prompt_hash` guarantees that even if you forget to increment the version label, the hash will differ between runs. A report with `prompt_hash="abc123"` is always traceable to the exact prompt content that produced it.

---

## Limitations

**Small dataset.** Four healing cases is enough to verify basic functionality but not enough to measure subtle quality differences. Expand the dataset before drawing strong conclusions from comparisons.

**Lexical checks.** Repair benchmarks check text patterns, not runtime correctness. A "passing" repair may still fail at runtime. Use the repair benchmark to filter out clearly wrong repairs, then run the surviving specs with Playwright to verify runtime correctness.

**Provider variance.** LM Studio and Ollama may use different inference engines or quantizations for the same model name. Record `model_version` (quantization) to make comparisons meaningful.
