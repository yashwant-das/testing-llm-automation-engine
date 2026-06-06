# Reproducibility

> How to ensure benchmark runs can be compared and reproduced.

---

## What Makes a Run Reproducible?

A run is reproducible if, given the same `BenchmarkRunConfig` and the same dataset, it produces the same results. For this to hold:

1. **Temperature must be 0.0.** At temperature > 0, the LLM introduces randomness. Two runs of the same model at temperature 0.1 may produce different code.
2. **The seed must be fixed.** Some inference engines use a seed for sampling. Pass `seed=42` (or any fixed value) to `BenchmarkRunConfig`.
3. **The prompt must be hashed, not just versioned.** The `prompt_hash` field records the SHA-256 of the actual prompt file content. If someone edits `healer.md` without incrementing the version, the hash will differ — the discrepancy is detectable.
4. **The dataset must be versioned.** The `dataset_version` field links the run to the exact set of cases that were evaluated.
5. **The model version must be recorded.** Same model name, different quantization or fine-tune = different results. Record `model_version` when the provider exposes it.

---

## BenchmarkRunConfig

Every run must supply a complete `BenchmarkRunConfig`:

```python
from schemas.evaluation import BenchmarkRunConfig
from src.utils.prompt_loader import get_prompt_hash, get_prompt_version

config = BenchmarkRunConfig(
    model="qwen3-coder-30b",           # model identifier
    model_version="q4_k_m",            # quantization / fine-tune variant
    provider="lm_studio",              # "lm_studio" | "ollama"
    prompt_name="healer",              # which prompt file
    prompt_version=get_prompt_version("healer"),   # "2" (from manifest.json)
    prompt_hash=get_prompt_hash("healer"),         # SHA-256 of healer.md
    temperature=0.0,                   # must be 0.0 for reproducibility
    seed=42,                           # fixed seed
    dataset_version="1.0.0",           # from repair_scenarios.json "version" field
    benchmark_type="healing",
)
```

---

## Prompt Hashing

`get_prompt_hash("healer")` computes the SHA-256 of `prompts/healer.md` and returns the first 16 hex characters. This is recorded in:

- `BenchmarkRunConfig.prompt_hash` — every benchmark run
- `HealingDecision.prompt_hash` — every healing artifact
- `TraceMetadata.prompt_hash` — every LLM span in traces

If two runs have the same `prompt_version` but different `prompt_hash`, the prompt was modified between runs. The hash is the source of truth.

---

## Heuristic Reproducibility

The heuristic classifier (`classify_failure_heuristic`) is fully deterministic — it uses regex patterns, not probabilistic models. A heuristic benchmark run is reproducible by definition, regardless of temperature or seed. This is why the Benchmark Explorer tab can run it with a single button click and always get the same result.

---

## Comparing Runs

Save every run to `benchmarks/reports/`:

```python
path = run.save_report(Path("benchmarks/reports/"))
```

Compare two runs by diffing the JSON files:

```bash
# Compare pass rates
jq '.passed, .total, .pass_rate' benchmarks/reports/run_A.json
jq '.passed, .total, .pass_rate' benchmarks/reports/run_B.json

# Find cases that changed from pass to fail
jq '.results[] | select(.passed==false) | .example_id' benchmarks/reports/run_B.json

# Compare config
jq '.config' benchmarks/reports/run_A.json
jq '.config' benchmarks/reports/run_B.json
```

If `prompt_hash` differs between two runs, the comparison is not apples-to-apples — the prompt changed.

---

## What Is Not Reproducible

**LLM outputs at temperature > 0.** Even with a fixed seed, some inference engines use time-based entropy. At temperature 0.1, the same prompt can produce slightly different code on repeated calls.

**Live page DOM.** Generation benchmarks that fetch real URLs are not reproducible across time — pages change. The current generation benchmark uses live URLs for realism. To make it fully reproducible, use a mocked or cached page snapshot.

**Model provider versions.** LM Studio and Ollama may update their quantization or inference engine between runs. If `model_version` is not recorded, you cannot know if a score change is due to your change or a provider update.
