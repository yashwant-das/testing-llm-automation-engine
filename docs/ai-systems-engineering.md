# AI Systems Engineering Guide

> This document uses the AI Testing Workbench as a reference implementation
> to explain the engineering patterns required to build reliable AI pipelines.
> Each section describes a concept, explains why it matters, and shows exactly
> where and how it is implemented in this codebase.

---

## Introduction

Building an application that calls an LLM is easy. Building one that is reliable, debuggable, measurable, and maintainable is hard. The gap between the two is AI Systems Engineering.

The AI Testing Workbench was built specifically to close this gap. Each of the eleven phases of its modernization program addressed a distinct reliability failure: fragile parsing, invisible failures, untestable architecture, unmeasurable quality, untraceble decisions. What remains is a system where every failure is diagnosable and every decision is explainable.

This guide explains the patterns that made that possible.

---

## Pattern 1: Structured Outputs

### The Problem

LLMs return text. Your program needs data. The naive approach is string parsing:

```python
# Fragile: breaks on any response variation
json_str = response.split("```json")[1].split("```")[0]
data = json.loads(json_str)
```

This approach fails silently. If the LLM adds a preamble, changes a field name, or omits a required field, you get either a KeyError or corrupt data downstream.

### The Solution

Define the expected output as a Pydantic schema. Parse every LLM response against that schema. On validation failure, retry or surface the error explicitly.

```python
# From src/utils/llm.py
def parse_llm_response(content: str, schema: type[T]) -> T:
    json_str = _extract_json_block(content)
    return schema.model_validate_json(json_str)
```

```python
# From src/healing/planner.py
analysis = parse_llm_response(raw_content, HealingAnalysis)
# If the LLM omits 'confidence_score', Pydantic raises ValidationError immediately.
# No silent corruption. No KeyError 10 calls later.
```

### Where It Lives

- Schema definitions: `schemas/` (5 modules, ~15 models)
- Parser: `src/utils/llm.parse_llm_response()`
- Validation on every LLM call: `planner.py`, `generator.py`, `vision.py`

### Why It Matters

Structured outputs convert your LLM from a text-returning black box into a typed function. Errors surface at the point of parsing, not 10 function calls later. Schema drift between the prompt and the code becomes visible immediately.

---

## Pattern 2: Hybrid Diagnosis (Deterministic + AI)

### The Problem

LLMs are probabilistic. For some failure types, you know exactly what to do: a `TimeoutError` with `5000ms exceeded` is always a timeout. Sending this to an LLM wastes tokens and adds latency.

### The Solution

Run a fast, deterministic classifier first. Only escalate to the LLM when the heuristic is uncertain.

```python
# From src/healing/planner.py
h_type, h_conf, h_reason = classify_failure_heuristic(evidence.error_log)
# ... call LLM ...
# If heuristic is confident and LLM says UNKNOWN, trust the heuristic:
if h_conf > 0.8 and analysis.failure_type == FailureType.UNKNOWN:
    analysis = analysis.model_copy(update={"failure_type": h_type})
```

The heuristic classifier (`src/healing/classifier.py`) uses regex patterns. It is:

- Zero-cost (no tokens, no latency)
- Fully deterministic (same input → same output, always)
- Independently testable (no LLM mock required)
- Right 100% of the time for the patterns it knows

The LLM handles everything the heuristic cannot classify.

### Where It Lives

- Heuristic classifier: `src/healing/classifier.py`
- Integration: `src/healing/planner.py`
- Tests: `tests/unit_test_classification.py`

### Why It Matters

A 100%-LLM pipeline is expensive and slow. A 100%-heuristic pipeline cannot handle novel failures. The hybrid approach gets the best of both: fast and cheap for known patterns, intelligent for everything else.

---

## Pattern 3: Model Routing with Retry and Fallback

### The Problem

LLM APIs are unreliable. Rate limits, connection timeouts, empty responses, and model overloads are normal operating conditions. A single-call pipeline fails in production.

### The Solution

Wrap every LLM call in a router that retries transient failures with exponential backoff and falls back to a secondary model when the primary is exhausted.

```python
# From src/llm/router.py (simplified)
for attempt in range(retry_policy.max_retries):
    try:
        response = client.chat.completions.create(...)
        return LLMResponse(content=response.choices[0].message.content, ...)
    except (RateLimitError, APIConnectionError):
        time.sleep(base_delay * (backoff_multiplier ** attempt))
# fallback to secondary model if configured
```

The `LLMResponse` carries `retry_count` — visible in artifacts, queryable in traces. If retries spike, you know your provider is having issues.

### Where It Lives

- Router: `src/llm/router.py`
- Retry policy: `src/llm/policies.py`
- Tests: `tests/unit_test_llm.py` (no live LLM required)

### Why It Matters

A pipeline that fails 5% of the time due to transient errors is untrustworthy. Retry + fallback brings that to near-zero without code changes in the callers.

---

## Pattern 4: Evaluation Frameworks

### The Problem

Without measurement, every change is a guess. You cannot know if a new prompt is better than the old one without running both against the same inputs and comparing outputs.

### The Solution

Build a dataset of labeled examples. Write pure evaluator functions. Record every run with full configuration metadata.

```python
# From benchmarks/healing/runner.py
def evaluate_classification(case: HealingCase, classified_type: str) -> bool:
    """Pure function — no I/O, no LLM, no side effects."""
    return classified_type == case.checks.expected_failure_type
```

A benchmark run records model + prompt_version + prompt_hash + temperature + seed + dataset_version. Two runs with the same config at `temperature=0` must produce the same results.

### Where It Lives

- Benchmark runners: `benchmarks/`
- Dataset files: `benchmarks/*/fixtures/*.json`
- Mutation engine: `benchmarks/mutations/mutator.py`
- Schemas: `schemas/evaluation.py`

### Key Insight

**Evaluation functions should be pure.** If `evaluate_classification(case, "TIMEOUT")` is a pure function, you can unit-test the evaluator without a dataset. You can also run 1000 synthetic cases in milliseconds. Side-effectful evaluators are hard to test and slow to run.

### Why It Matters

Evaluation is how you turn "I think this is better" into "this is 15% better on the repair benchmark." Without it, you are making decisions based on vibes.

---

## Pattern 5: Deterministic vs AI Repair

### The Problem

LLMs produce approximate text. A selector change proposed by an LLM may not exactly match the source code — especially if the LLM adds or removes whitespace. String replacement against approximate text fails silently.

### The Solution

Use AST transformations for structural repairs. The AST understands the code; string matching does not.

```text
User requests: "rename selector '#old-btn' to '#new-btn'"

String approach: search for '#old-btn' in the file → replace
  Problem: misses occurrences with different whitespace
  Problem: cannot rename only in locator contexts

AST approach: walk the TypeScript AST → find all CallExpression nodes
  where callee is a locator function → replace the argument string
  Result: all occurrences updated correctly, regardless of whitespace
```

The AST repair runs as a Node.js subprocess (`scripts/ast_repair.js`) with a typed JSON protocol. If the AST produces 0 changes, the pipeline falls back to the string approach. If string also fails, the original code is returned unchanged.

### Where It Lives

- Python orchestration: `src/healing/repair.py`
- TypeScript AST script: `scripts/ast_repair.js`
- Strategy enum: `schemas/healing.RepairStrategy`

### Why It Matters

String replacement is fragile against real code. AST transformation is robust against whitespace, comments, and multi-occurrence repairs. The hybrid (AST first, string fallback) gives you correctness where possible and graceful degradation where not.

---

## Pattern 6: Explainability

### The Problem

An AI system that outputs decisions without explaining them cannot be trusted. If the healer changes a selector and the change breaks something else, you need to understand: why did it choose that selector? How confident was it? What evidence did it use?

### The Solution

Record provenance on every decision artifact. Not just what was decided, but why, with what inputs, at what confidence, and using which model and prompt.

```python
class HealingDecision(BaseModel):
    # What was decided
    failure_type: FailureType
    hypothesis: str
    confidence_score: float
    action_taken: HealingAction

    # Why (LLM's own reasoning)
    reasoning_steps: List[str]
    confidence_rationale: str        # "Confidence 0.95 because selector error is unambiguous"
    root_cause_evidence: List[str]   # ["Error: locator('#old-btn') resolved to 0 elements"]

    # With what inputs
    context_snapshot_id: str         # SHA-256 of error_log — identifies the evidence

    # Using which model and prompt
    model_used: str                  # "qwen3-coder-30b"
    prompt_version: str              # "2" (from manifest.json)
    prompt_hash: str                 # SHA-256 of healer.md content
    execution_duration_ms: int       # Wall-clock time for the planning call
```

`to_markdown()` renders all of this in a human-readable report.

### Where It Lives

- Schema: `schemas/healing.HealingDecision`
- Prompt manifest: `prompts/manifest.json`
- Planner: `src/healing/planner.py` (populates all provenance fields)

### Why It Matters

Explainability converts an AI decision from "the machine changed this" to "the machine changed this because it saw this error, classified it as a locator drift with 95% confidence because the log line is unambiguous, and used model X at prompt version 2." The latter is reviewable, auditable, and trustworthy.

---

## Pattern 7: Observability

### The Problem

Without tracing, you cannot answer: how many tokens did that healing session use? How long did the LLM call take? Did the classifier get it right? Was there a retry?

### The Solution

Instrument every LLM call and every subprocess call. Link them to a session via a `trace_id`. Write structured spans to a queryable format.

```python
# Every LLM call is automatically recorded in LLMRouter._build_response()
tracer.record_llm_response(response)
# → writes {"span_type":"llm","trace_id":"...","model":"...","input_tokens":4821,...}

# Every subprocess call is recorded in runner.run_test()
tracer.record_subprocess(command=cmd, exit_code=code, latency_ms=latency)
# → writes {"span_type":"subprocess","trace_id":"...","exit_code":0,"latency_ms":7100,...}

# Session aggregates both at end
tracer.end_session(trace_id, success=True)
# → writes {"span_type":"session","trace_id":"...","llm_call_count":1,"total_input_tokens":4821,...}
```

### Thread Safety

Gradio runs event handlers on separate threads. Sessions are stored in `threading.local()` — each thread has its own session with no cross-contamination.

### Where It Lives

- Tracer: `src/observability/tracer.py`
- Writer: `src/observability/writer.py`
- Instrumentation points: `src/llm/router.py`, `src/healing/runner.py`, `src/services/healing_service.py`

### Why It Matters

Observability is how you move from "I think the LLM is slow" to "the LLM averaged 3.4 seconds per call with 4,821 input tokens, and there were 3 retries across 10 sessions." That data drives optimization.

---

## Pattern 8: Reproducibility

### The Problem

If you cannot reproduce a result, you cannot trust it. If changing the temperature changes the benchmark score, your evaluation is measuring noise, not quality.

### The Solution

Record every input to every run. Use `temperature=0.0` for benchmarks. Use a fixed seed. Hash the prompt content — not just the version label.

```python
class BenchmarkRunConfig(BaseModel):
    model: str
    prompt_version: str      # human-set label (e.g. "2")
    prompt_hash: str         # SHA-256 of actual prompt content
    temperature: float = 0.0
    seed: Optional[int]
    dataset_version: str     # from the dataset JSON file
```

The `prompt_hash` catches the case where someone edits the prompt file without incrementing the version. Two runs with the same `prompt_version` but different `prompt_hash` used different prompts — detectable in the run record.

### Where It Lives

- Run config schema: `schemas/evaluation.BenchmarkRunConfig`
- Hash computation: `src/utils/prompt_loader.get_prompt_hash()`
- Manifest: `prompts/manifest.json`

### Why It Matters

Reproducibility is the difference between a result you can share and a result only you can see. An evaluation framework without reproducibility is just logging.

---

## Pattern 9: The Service Layer Boundary

### The Problem

UI frameworks like Gradio have specific requirements: streaming callbacks, file handling, event loops. If business logic lives in event handlers, it cannot be tested independently of the UI.

### The Solution

Define a strict boundary. The UI layer imports only from `src/services/`. The service layer imports from the pipeline. No pipeline imports in the UI.

```python
# app.py — only imports from services
from src.services.generation_service import generate_test_streaming
from src.services.healing_service import heal_test_streaming
from src.services.workbench_service import run_classification_benchmark

# healing_service.py — imports from pipeline
from src.healing import analyze_and_plan, apply_fix, gather_evidence
```

Services are generator functions that `yield` progress tuples. Gradio's `yield`-based streaming model maps directly to this — no async, no callbacks, no event bus.

### Where It Lives

- Service layer: `src/services/`
- UI: `src/app.py`
- ADR: `docs/decisions.md` — ADR-006

### Why It Matters

A service layer boundary makes pipeline modules independently testable. It lets you run the healing pipeline from a CLI, a test harness, or a different UI without changing any business logic.

---

## Summary: The Engineering Checklist

For any AI pipeline, ask:

- [ ] Are LLM responses validated against a schema before use? (Pattern 1)
- [ ] Is there a deterministic fast path for known cases? (Pattern 2)
- [ ] Does every LLM call retry on transient failures? (Pattern 3)
- [ ] Is there a benchmark dataset to measure quality changes? (Pattern 4)
- [ ] Are code mutations applied with semantic precision (AST), not string approximation? (Pattern 5)
- [ ] Does every decision artifact carry enough provenance to reproduce and audit it? (Pattern 6)
- [ ] Is every LLM call and subprocess call traced with a shared session ID? (Pattern 7)
- [ ] Are evaluation runs reproducible at temperature 0 with a fixed prompt hash? (Pattern 8)
- [ ] Is the UI isolated from business logic by a service layer? (Pattern 9)

A system that satisfies all nine is not just an AI application — it is a trustworthy AI system.
