# Observability Tool Evaluation

> Phase 8 prerequisite — evaluates observability approaches before implementation.
> Decision recorded in `decisions.md` ADR-004.

---

## Problem Statement

No trace IDs. No token usage persistence. No latency metrics. No retry counts.
`LLMRouter` already logs these values to stdout via Python's `logging` module, but
they are not persisted, not linked to sessions, and not queryable after the fact.

Every healing session produces a JSON artifact (`tests/artifacts/*.json`) but there
is no way to ask: "How many tokens did the healer consume per session?" or
"Which pipeline stage caused the most latency?".

---

## Evaluation Criteria

| Criterion | Weight | Notes |
| --- | --- | --- |
| Local-first (no cloud required) | HIGH | Must work with no external services |
| Zero new dependencies | HIGH | "Prefer deletion over addition" principle |
| LLM-native signals | HIGH | Token counts, model name, prompt version |
| Thread-safe | HIGH | Gradio event handlers run concurrently |
| Human-readable output | MEDIUM | Debuggable without specialized tooling |
| Query-able output | MEDIUM | `jq`, grep, or a UI |
| Minimal code surface | HIGH | Single-engineer project |

---

## Candidates

### Option A: OpenTelemetry SDK (Python)

**What it is:** The industry-standard observability API; OTLP exporter sends spans to
Jaeger, Tempo, or stdout.

**Fit assessment:**

| Criterion | Score | Reason |
| --- | --- | --- |
| Local-first | ✅ | Stdout exporter works without a collector |
| Zero new deps | ❌ | `opentelemetry-sdk` + `opentelemetry-api` (~5 MB, 3 transitive packages) |
| LLM-native signals | ⚠️ | Must add custom attributes for token counts; no native LLM span type |
| Thread-safe | ✅ | Built-in context propagation |
| Human-readable | ⚠️ | JSON spans are verbose; stdout output is noisy |
| Query-able | ✅ | Works with any OTEL-compatible backend |
| Minimal code surface | ⚠️ | Tracer, span, context — unfamiliar API for a simple pipeline |

**Verdict:** Appropriate if the project ever needs to export to Jaeger or Datadog.
Unjustified overhead for a local, single-engineer tool.

---

### Option B: Langfuse (self-hosted)

**What it is:** LLM-native observability platform with native prompt/completion view,
cost tracking, and evaluation UI. Can be self-hosted with Docker.

**Fit assessment:**

| Criterion | Score | Reason |
| --- | --- | --- |
| Local-first | ✅ | Docker Compose self-hosting is supported |
| Zero new deps | ❌ | `langfuse` Python SDK (~3 MB) + Docker + Postgres |
| LLM-native signals | ✅ | Native prompt/completion view, token counts, cost |
| Thread-safe | ✅ | SDK handles async flushing |
| Human-readable | ✅ | Web UI with trace view |
| Query-able | ✅ | Full SQL via Postgres or the Langfuse UI |
| Minimal code surface | ⚠️ | Requires Docker and a Postgres instance |

**Verdict:** Excellent choice once the project is ready for a heavier observability
investment. The Docker requirement is not "local-first" for a project that runs with a
single `python` command. Deferred — the instrumentation layer built in Phase 8 is
designed to forward spans to Langfuse in a future phase with minimal code changes.

---

### Option C: Langfuse (cloud)

**What it is:** Same as Option B but hosted at `cloud.langfuse.com`.

**Fit assessment:**

| Criterion | Score | Reason |
| --- | --- | --- |
| Local-first | ❌ | Data leaves the machine |
| Zero new deps | ⚠️ | `langfuse` Python SDK still required |
| LLM-native signals | ✅ | Same as self-hosted |
| Thread-safe | ✅ | |
| Human-readable | ✅ | |
| Query-able | ✅ | |
| Minimal code surface | ✅ | No Docker |

**Verdict:** Rejected. Data exfiltration is a non-starter for a project that may
process sensitive test code.

---

### Option D: Custom JSONL Tracer (zero dependencies) ✅ SELECTED

**What it is:** A Python module in `src/observability/` that writes structured spans
as newline-delimited JSON to `logs/traces.jsonl`. No new pip dependencies.

**How it works:**

1. `healing_service.py` calls `tracer.start_session("healing")` → returns a `trace_id`.
2. The tracer stores the active session in a `threading.local()` — one session per thread.
3. `LLMRouter._build_response()` calls `get_tracer().record_llm_response(llm_response)` — recorded silently.
4. `run_test()` calls `get_tracer().record_subprocess(...)` after each subprocess call.
5. `healing_service.py` calls `tracer.end_session(trace_id)` → writes a `SessionSpan` aggregating all child spans.

**Span types:**

- `TraceMetadata` (LLM call) — model, tokens, latency, retry_count, prompt_hash
- `SubprocessSpan` (Playwright subprocess) — command, exit_code, latency_ms
- `SessionSpan` (end-to-end) — aggregated totals, success/failure

**Querying traces:**

```bash
# Total tokens per session
jq 'select(.span_type == "session") | {trace_id, total_input_tokens, total_output_tokens}' logs/traces.jsonl

# All LLM calls with retries
jq 'select(.span_type == "llm" and .retry_count > 0)' logs/traces.jsonl

# Slowest pipeline stages
jq 'select(.span_type == "subprocess") | {command, latency_ms}' logs/traces.jsonl | sort
```

**Fit assessment:**

| Criterion | Score | Reason |
| --- | --- | --- |
| Local-first | ✅ | Pure file I/O |
| Zero new deps | ✅ | No new packages |
| LLM-native signals | ✅ | Custom span fields: model, tokens, prompt_hash |
| Thread-safe | ✅ | `threading.Lock()` on file write |
| Human-readable | ✅ | JSONL is readable with cat / jq / any text editor |
| Query-able | ✅ | `jq` provides SQL-like queries without setup |
| Minimal code surface | ✅ | ~200 lines total |

**Future upgrade path:** The span schemas are designed to be compatible with OTEL
semantic conventions. When Langfuse self-hosted becomes practical, a
`LangfuseExporter` can replace `TraceWriter` without changing the tracer API.

**Verdict:** Selected. Satisfies all constraints. Zero-dependency, local-first,
queryable, and extensible.

---

## Decision Summary

**Selected:** Option D — Custom JSONL Tracer

**Reasoning:**

1. The project already violates "prefer deletion over addition" zero times in Phase 8.
   Adding 5+ MB of OTEL packages would be the first violation.
2. `LLMRouter` already captures all required signals (`LLMResponse` has model, tokens,
   latency, retry_count). The tracer needs only to persist and link them.
3. JSONL + `jq` satisfies all query needs for a single-engineer project.
4. The design is forward-compatible with OTEL and Langfuse for future phases.

**Revisit trigger:** When the project gains a second engineer or needs a web-based
trace UI. At that point, Langfuse self-hosted is the recommended next step.

See `decisions.md` ADR-004 for the formal record.
