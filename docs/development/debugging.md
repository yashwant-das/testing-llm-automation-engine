# Debugging Guide

> Common failure modes and how to diagnose them.

---

## Anatomy of a Failure

Every healing session produces two artifacts:

- `tests/artifacts/healing_decision_<timestamp>.json` — the full `HealingDecision` schema
- `logs/traces.jsonl` — one JSONL line per span: session, LLM call, subprocess call

Both are available in the **Artifact Inspector** and **Trace Inspector** tabs of the Workbench.

---

## Failure Mode 1: LLM Returns No Valid JSON

**Symptom**: `HealingDecision.action_taken` is `"no-change"` with `failure_type` set to `UNKNOWN`.

**Cause**: The LLM output did not contain a JSON code block. The planner falls back to a safe `HealingDecision` with `action_taken="no-change"`.

**Diagnose**:

1. Load the artifact in the Artifact Inspector and check `root_cause_evidence` and `confidence_rationale`
2. Load traces and find the LLM span — check the `prompt_version` and raw `model_used`
3. Enable Python logging to see the raw LLM response:

```bash
LLM_DEBUG=1 uv run python src/app.py
# or directly:
uv run python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from src.healing.planner import analyze_and_plan
from src.schemas.healing import Evidence
e = Evidence(error_log='Error: locator.click ...')
d = analyze_and_plan('test.spec.ts', open('tests/fixtures/example.spec.ts').read(), e)
print(d.model_dump_json(indent=2))
"
```

**Fix**: If the model is producing prose instead of JSON, check that `prompts/healer.md` contains the exact JSON schema in a fenced code block. Some models ignore the schema if the prompt is long — try switching to a larger context model.

---

## Failure Mode 2: AST Repair Makes No Changes

**Symptom**: `action_taken` is `"string-fallback"` or `"no-change"`. The repair log shows `"strategy": "string_fallback"` or `"strategy": "unchanged"`.

**Cause**:

- The `original_code` snippet in `HealingDecision` does not appear verbatim in the test file
- All 5 AST strategies produced 0 matching nodes
- The LLM suggested a repair for code that does not exist in the file

**Diagnose**:

```bash
# Look at the subprocess span in traces
jq 'select(.span_type == "subprocess")' logs/traces.jsonl | \
  jq '{action: .action, exit_code: .exit_code, strategy: .strategy_used}'

# Check the artifact for the suggested repair
jq '{original_code, fixed_code, action_taken}' \
  tests/artifacts/healing_decision_<timestamp>.json
```

Check whether `original_code` matches anything in the actual test file:

```bash
grep -F "$(jq -r '.original_code' tests/artifacts/healing_decision_<timestamp>.json)" \
  tests/my_test.spec.ts
```

**Fix**: This is usually an LLM hallucination — the model invented `original_code` that is similar but not identical to what is in the file. No code fix is needed; the architecture handles this via the string fallback and unchanged-code safety net. If it happens repeatedly, review the prompt in `prompts/healer.md` and ensure the injected code block matches the actual file content (check `planner.py::_build_prompt`).

---

## Failure Mode 3: Classification is UNKNOWN

**Symptom**: `failure_type` is `UNKNOWN` and `confidence_score` is below 0.5.

**Cause**: The error log does not match any heuristic pattern in `classifier.py`, and the LLM also returned `UNKNOWN` or the LLM call failed.

**Diagnose**:

```python
from src.healing.classifier import classify_failure_heuristic

log = """<paste error log here>"""
f_type, confidence, reason = classify_failure_heuristic(log)
print(f"type={f_type}, confidence={confidence}, reason={reason}")
```

If heuristic returns `UNKNOWN`, check whether the error log format has changed (e.g., Playwright version upgrade). The patterns are all in `src/healing/classifier.py`.

**Fix**: Add a new regex pattern to `classify_failure_heuristic()` and add a test case in `unit_test_classification.py`. See [Adding a Benchmark](adding-benchmarks.md) for how to add a classification benchmark case to validate it.

---

## Failure Mode 4: Healing Pipeline Does Not Start

**Symptom**: UI shows an error immediately when clicking "Heal" — no artifact is created.

**Cause options**:

- LLM server is not running
- Playwright could not open the browser (for context collection)
- Test file path does not exist

**Diagnose**:

```bash
# Check LLM connectivity
curl http://localhost:1234/v1/models   # LM Studio
curl http://localhost:11434/v1/models  # Ollama

# Verify Node.js (required for AST repair)
node --version
node scripts/ast_repair.js  # should print usage

# Check the Python logging output in terminal where app.py runs
```

---

## Failure Mode 5: Traces File Not Growing

**Symptom**: `logs/traces.jsonl` is empty or stuck at a previous run.

**Cause**: The tracer is the `NullTracer` (default) — `configure_tracer()` was not called with a real writer.

**Check**:

```python
from src.observability import get_tracer
t = get_tracer()
print(type(t).__name__)   # NullTracer if not configured, Tracer if configured
```

In `src/app.py`, `configure_tracer()` is called at startup. If you are running pipeline code directly (not through the app), call `configure_tracer()` first:

```python
from src.observability import configure_tracer
configure_tracer()  # writes to logs/traces.jsonl
```

---

## Reading Traces

The `logs/traces.jsonl` file contains one JSON object per line. Three span types:

```bash
# All sessions (one per healing run)
jq 'select(.span_type == "session")' logs/traces.jsonl | \
  jq '{session_id, test_file, failure_type, duration_ms}'

# All LLM calls with prompt info
jq 'select(.span_type == "llm")' logs/traces.jsonl | \
  jq '{session_id, model, prompt_name, prompt_version, prompt_hash, latency_ms, retry_count}'

# All subprocess calls (AST repair)
jq 'select(.span_type == "subprocess")' logs/traces.jsonl | \
  jq '{session_id, command, exit_code, strategy_used, duration_ms}'

# Slowest LLM calls
jq 'select(.span_type == "llm") | {model, latency_ms, session_id}' logs/traces.jsonl | \
  jq -s 'sort_by(-.latency_ms) | .[0:5]'

# Failed LLM calls (retry_count > 0)
jq 'select(.span_type == "llm" and .retry_count > 0)' logs/traces.jsonl
```

---

## Reading Healing Decision Artifacts

```bash
# Summary of all artifacts
for f in tests/artifacts/healing_decision_*.json; do
  jq -r '"[\(input_filename)]: type=\(.failure_type) action=\(.action_taken) confidence=\(.confidence_score)"' "$f"
done

# Full provenance of a specific run
jq '{failure_type, confidence_score, confidence_rationale, root_cause_evidence, model_used, prompt_version, prompt_hash, execution_duration_ms}' \
  tests/artifacts/healing_decision_<timestamp>.json
```

---

## Python Logging

All pipeline modules use the standard `logging` module with `getLogger(__name__)`. Enable debug output:

```bash
# All pipeline logging at DEBUG level
PYTHONPATH=. uv run python -c "
import logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s %(levelname)s: %(message)s')
# ... run code ...
"
```

Key loggers:

- `src.healing.planner` — LLM call, fallback decisions
- `src.healing.repair` — AST strategy chosen, fallback warnings
- `src.healing.classifier` — classification result
- `src.llm.router` — retry logic, provider switching
- `src.context.*` — context collection per module
