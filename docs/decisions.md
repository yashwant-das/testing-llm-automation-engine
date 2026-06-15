# Architecture Decision Records

> ADR format: Context → Decision → Alternatives → Consequences.
> Every major technical decision must be recorded here before implementation.

---

## ADR-001: Pydantic over dataclasses for schemas

**Date:** 2026-06-06
**Status:** DECIDED

### Context

`src/models/healing_model.py` uses Python `@dataclass` for `HealingDecision`, `Evidence`, `HealingAction`, and `ExecutionTimeline`. Dataclasses provide no runtime validation, no schema export, and no integration with structured output tools.

### Decision

Replace all `@dataclass` models with Pydantic `BaseModel` subclasses, housed in a new top-level `schemas/` directory.

### Alternatives Considered

- **Keep dataclasses + add manual validation:** More code, no schema export, still no retry-on-parse-failure.
- **attrs:** Validation via validators, but no JSON schema generation, less OpenAI tool_call integration.
- **msgspec:** Fastest option, but less ecosystem support and no native OpenAI schema integration.
- **Pydantic v2:** Native JSON schema generation, OpenAI `response_format` integration, field validators, coercion. Already installed as a transitive dependency.

### Consequences

- **Positive:** Schema enforcement at parse time; retry on validation failure; JSON schema exportable for OpenAI `response_format`; IDE completions.
- **Negative:** Slight performance overhead (irrelevant at this scale); Pydantic v2 API requires learning validators and `model_config`.
- **Migration:** Existing artifact JSON files remain valid; Pydantic will parse them. Unit tests will need minor updates to use `model_validate()` instead of constructor.

---

## ADR-002: LiteLLM for provider routing

**Date:** 2026-06-06
**Status:** SUPERSEDED by ADR-007

See ADR-007 for the implemented decision.

---

## ADR-003: AST tool selection for TypeScript repair

**Date:** 2026-06-06
**Status:** DECIDED

### Context

`apply_fix()` in `src/healing/repair.py` repairs tests using string replacement with
sliding-window indentation normalization. Structural repairs (add import, rename locator
across file, change test structure) are not possible without AST access.

### Decision

**Use ts-morph** via Node.js subprocess with a typed JSON stdin/stdout protocol.

### Rationale

- **TypeScript-native:** Built on the TypeScript compiler API — full TypeScript understanding
  including generics, decorators, and template literals.
- **Read/write AST:** Node replacement, insertion, deletion — formatting-preserving.
- **Zero new runtime deps beyond what Playwright already requires:** Node.js is already
  present; `typescript` is already a devDependency. Only `ts-morph` is new.
- **Subprocess isolation:** The AST script runs in a separate Node.js process. Any crash
  or timeout in the script does not affect the Python healing pipeline.
- **Typed JSON protocol:** Python sends `{ strategy, source, original_code, fixed_code }`
  on stdin; Node.js returns `{ success, source, changes }` on stdout.

### Alternatives Rejected

- **Babel:** TypeScript support is second-class (strips types); adds dependencies on top
  of `typescript` which is already installed.
- **tree-sitter:** Read-only parse trees; mutations are still string-based; Python native
  bindings add build complexity.
- **SWC:** Designed for compilation/bundling; programmatic mutation API is experimental
  Rust-only.

### Consequences

- **Positive:** Structural repairs (add import, multi-site selector rename, timeout
  adjustment, assertion swap) all become possible without regex fragility.
- **Negative:** Node.js subprocess adds ~50ms latency per repair call. Acceptable given
  healing sessions take seconds to minutes.
- **Fallback retained:** String replacement remains the default; AST is tried first when
  `repair_strategy` is set to a non-`string_replace` value. String fallback fires if AST
  produces no changes.
- **Revisit trigger:** If Playwright drops Node.js as a dependency (extremely unlikely).

---

## ADR-004: Observability tool selection

**Date:** 2026-06-06
**Status:** DECIDED

### Context

No observability exists. Token usage, latency, retry counts, and failure patterns are invisible. Running a healing session produces JSON artifacts but no queryable traces.

### Decision

**Custom JSONL Tracer** (`src/observability/`) — zero new dependencies.

Span types: `TraceMetadata` (LLM call), `SubprocessSpan` (Playwright subprocess),
`SessionSpan` (end-to-end healing/generation session). All spans written to
`logs/traces.jsonl` as newline-delimited JSON, queryable with `jq`.

### Rationale

- `LLMRouter` already captures all required signals in `LLMResponse`. The tracer
  only needs to persist and link them.
- Adding `opentelemetry-sdk` (~5 MB) violates "prefer deletion over addition".
- Langfuse self-hosted requires Docker — incompatible with single-command startup.
- JSONL + `jq` satisfies all query needs for a single-engineer project.

### Alternatives Rejected

- **OpenTelemetry SDK:** Appropriate if multiple exporters or backend integration is
  needed. Revisit when the project gains a second engineer.
- **Langfuse self-hosted:** Revisit when a web trace UI becomes a priority.
- **Langfuse cloud:** Rejected — data exfiltration risk for test code.

### Consequences

- **Positive:** Zero new dependencies; local-first; human-readable; queryable with jq.
- **Negative:** No web UI; no alerting; no cost aggregation dashboard.
- **Upgrade path:** Span schemas designed to be compatible with OTEL semantic
  conventions. Swap `TraceWriter` for a `LangfuseExporter` to migrate without
  changing the tracer API.
- **Revisit trigger:** Project gains a second engineer, or web-based trace UI
  becomes a requirement.

---

## ADR-005: Keep prompts as external markdown files

**Date:** 2026-06-06
**Status:** DECIDED

### Context

Prompts live in `prompts/*.md` and are loaded at runtime by `prompt_loader.py`. Some systems embed prompts as Python string constants.

### Decision

Keep external markdown files. Add versioning via a `prompts/manifest.json` that maps prompt names to version strings and content hashes.

### Alternatives Considered

- **Inline string constants:** Harder to edit (requires Python syntax awareness), no diffing, no version history separate from code.
- **Database-backed prompts:** Over-engineered for single-engineer project.
- **External service (Langfuse prompt management):** Good option once Langfuse is integrated; deferred to Phase 8.

### Consequences

- **Positive:** Prompts remain diffable, human-editable, independently versioned.
- **Negative:** File I/O on every call (mitigated by caching in prompt_loader).
- **Resolved (Phase 9):** `prompts/manifest.json` implemented with version and hash fields. `prompt_loader.py` exposes `get_prompt_version()` and `get_prompt_hash()`. Both recorded in every `HealingDecision` artifact.

---

## ADR-006: Service layer between UI and agents

**Date:** 2026-06-06
**Status:** DECIDED

### Context

`src/app.py` currently imports agent internals directly and reimplements orchestration logic. This makes the agents untestable in isolation from the UI.

### Decision

Introduce `src/services/` as the boundary between UI and agents. The UI imports only from `src/services/`. Services import from agents. No agent imports in `app.py`.

### Alternatives Considered

- **Wire UI directly to agent module public APIs:** Simpler, but `app.py` still becomes coupling point for streaming callbacks.
- **Event bus / message queue:** Over-engineered; adds complexity without benefit at this scale.
- **Service layer with async generators:** Allows progressive streaming; matches Gradio's `yield`-based progress model.

### Consequences

- **Positive:** `app.py` shrinks dramatically; agents testable independently; streaming logic centralized in services.
- **Negative:** One additional layer of indirection.
- **Implementation Note:** Services use Python generator functions (yield) to provide streaming progress events to Gradio.

---

## ADR-007: OpenAI SDK wrapper instead of LiteLLM

**Date:** 2026-06-06
**Status:** DECIDED (supersedes ADR-002)

### Context

ADR-002 proposed LiteLLM as the routing layer. Phase 2 was the implementation point.
The project uses exactly two providers: LM Studio and Ollama. Both expose an
OpenAI-compatible REST API at a configurable `base_url`.

### Decision

Implement the LLM layer as a thin wrapper around the existing `openai` SDK
(`src/llm/` package) rather than adding LiteLLM.

### Rationale

- **LiteLLM's value is provider abstraction.** It normalises APIs from OpenAI, Anthropic,
  Cohere, Bedrock, etc. This project uses only OpenAI-compatible local endpoints.
  LiteLLM's abstraction adds nothing that `openai.OpenAI(base_url=...)` doesn't already do.
- **Dependency weight.** LiteLLM is a large package (40 MB+) with its own transitive
  dependency tree (httpx, aiohttp, pydantic, anthropic, …). Adding it violates the
  "prefer deletion over addition" principle.
- **Retry and fallback are simple.** The retry loop is ~30 lines. Fallback is a second
  `OpenAI` client. This does not justify a 40 MB dependency.
- **Testability.** The custom `LLMRouter` is easily unit-tested by mocking
  `LLMClientFactory.create`. LiteLLM's global state makes mocking harder.

### What was built instead

```text
src/llm/
├── client.py     — ProviderConfig (Pydantic) + LLMClientFactory (static, no side effects)
├── registry.py   — ModelCapabilities + ModelRegistry (capability metadata)
├── policies.py   — RetryPolicy + TimeoutPolicy (Pydantic config models)
├── router.py     — LLMRequest + LLMResponse (Pydantic) + LLMRouter (retry + fallback)
└── __init__.py   — public API + get_default_router() lazy singleton
```

### Alternatives Considered

- **LiteLLM:** Appropriate if the project ever needs to route to Anthropic, Bedrock, or
  other non-OpenAI-compatible providers. Should be revisited if that requirement arises.
- **Direct httpx:** Maximum control, but reimplements streaming and error handling already
  covered by the OpenAI SDK.
- **LangChain:** Over-engineered for this scope.

### Consequences

- **Positive:** No new dependencies; full control over retry/fallback/logging;
  all router logic unit-tested without mocking a third-party library.
- **Negative:** If a non-OpenAI-compatible provider is needed in the future,
  the router will need a new client backend. LiteLLM remains the right choice for that case.
- **Revisit trigger:** A third provider with a non-OpenAI-compatible API.

---

## ADR-008: Single browser session for context collection

**Date:** 2026-06-06
**Status:** DECIDED (Phase 6)

### Context

`src/context/` collects 6 types of page context for healing and generation: DOM, accessibility tree, locator candidates, console errors, network errors, and screenshot. A naive implementation launches a Playwright browser once per context type.

### Decision

Open exactly one Playwright browser session in `collect_context()` and pass the `page` object to all sub-collectors. Close the session after all collectors complete.

### Rationale

- **Browser startup is expensive** (~300–500ms per browser launch). Collecting 6 context types sequentially with separate launches adds ~2s to every healing session.
- **Consistent page state.** If the page is loaded once and all context is collected from the same DOM snapshot, the accessibility tree and DOM are guaranteed to be consistent with each other.
- **Simpler cleanup.** One `async with` block owns the browser lifetime — no risk of leaked browsers if a sub-collector raises.

### Alternatives Rejected

- **One browser per collector:** Each collector fetches a fresh page state. Adds latency and risks inconsistent snapshots across context types.
- **Parallel collectors:** Would require multiple browser sessions or careful sharing of a single Playwright page across async tasks. No meaningful latency benefit since context collection is I/O-bound sequentially.

### Consequences

- **Positive:** ~300ms per healing session saved. Consistent snapshots. Easier to mock in tests (one `page` mock, not one per collector).
- **Negative:** If one collector hangs, all subsequent collectors are blocked. Mitigated by per-collector timeouts.
- **Testability:** All collector functions accept a `page: Page` argument — tests inject a `MagicMock()` without launching a browser.

---

## ADR-009: Evaluation framework design

**Date:** 2026-06-06
**Status:** DECIDED (Phase 7)

### Context

The evaluation framework must answer "did this change improve results?" without requiring a live LLM, live browser, or network access. The framework must be runnable in CI.

### Decision

Three design principles:

1. **Pure evaluator functions** — no I/O, no LLM, no side effects. Inputs are the benchmark case and the output to evaluate. Output is an `EvaluationResult` Pydantic model.
2. **Classification-only as the default benchmark** — heuristic classification is deterministic and LLM-free. The classification benchmark runs in <1s.
3. **Injectable generator/healer functions** — LLM-dependent benchmarks accept a `generator_fn` argument so tests can inject a mock and run without a live LLM.

### Rationale

- Pure evaluators can be unit-tested trivially. A test that calls `evaluate_healing_case(case, output)` is deterministic and fast.
- The classification benchmark validates the heuristic classifier without any LLM dependency — CI can run it in <1s.
- Injectable functions allow future LLM benchmarks to be tested with mocked generators in CI, while production runs use real generators.

### Alternatives Rejected

- **Evaluators call the LLM to score outputs (LLM-as-judge):** Non-deterministic, expensive, requires credentials in CI.
- **Evaluators check runtime behaviour (spawn a browser to verify the repaired test passes):** Very slow, requires a running web server, not feasible in lightweight CI.

### Consequences

- **Positive:** Every evaluator is unit-testable. Classification benchmark runs in CI without credentials.
- **Negative:** Lexical checks (must_contain, must_import) are necessary simplifications. They do not validate semantic correctness.
- **Revisit trigger:** When LLM-as-judge is needed for semantic evaluation, add it as an optional `scorer_fn` argument to runners, not as a change to existing evaluators.

---

## ADR-010: Thread-local session isolation for Gradio

**Date:** 2026-06-06
**Status:** DECIDED (Phase 8)

### Context

Gradio runs each UI event handler in its own thread. The observability tracer must maintain one active session per healing/generation run. A global `session` variable would cause race conditions when two users trigger healing simultaneously.

### Decision

Use `threading.local()` to store the active `TracerSession` object. Each thread has its own `_thread_local.session` attribute. The tracer reads and writes only the session for the current thread.

### Rationale

- Gradio's threading model is one-thread-per-event-handler — `threading.local()` is the standard Python mechanism for this pattern.
- The alternative (asyncio) would require Gradio to support async handlers, which it does but with different semantics that complicate testing.
- Thread-local storage is zero-dependency and has no runtime overhead.

### Alternatives Rejected

- **Global session with a lock:** Serializes all healing sessions — unacceptable latency.
- **Session ID passed explicitly through every function:** Would require changing every pipeline function signature.
- **asyncio + contextvars:** More semantically correct for async code, but Gradio's event system uses threads, not coroutines.

### Consequences

- **Positive:** Complete isolation between concurrent healing sessions. No lock contention.
- **Negative:** Thread-local state is not visible across threads — if a session spawns a worker thread, that worker cannot see the tracer session. Currently not an issue since the pipeline is single-threaded per healing run.
- **Testability:** Tests that call `start_session()` must reset `_thread_local.session = None` in `tearDown` to avoid state leakage between tests running in the same thread.

---

## ADR-011: Healer decomposition into 7 modules

**Date:** 2026-06-06
**Status:** DECIDED (Phase 4)

### Context

The original `src/agents/healer.py` was a god module: 600+ lines mixing failure classification, evidence gathering, LLM prompt construction, LLM response parsing, AST repair, string repair, verification, and artifact persistence.

### Decision

Decompose `src/agents/healer.py` into 7 focused modules in `src/healing/`:

| Module              | Single Responsibility                         |
| ------------------- | --------------------------------------------- |
| `classifier.py`     | Heuristic failure classification              |
| `evidence.py`       | Evidence → HealingDecision field extraction   |
| `planner.py`        | LLM prompt construction and response parsing  |
| `repair.py`         | AST and string repair dispatch                |
| `verifier.py`       | Playwright test re-run and result parsing     |
| `artifact_store.py` | JSON artifact persistence                     |
| `runner.py`         | Orchestration — calls the 6 above in sequence |

### Rationale

- Each module is independently testable. `classifier.py` tests need no mocks. `planner.py` tests mock only the LLM router. `repair.py` tests mock only the subprocess.
- The single-responsibility boundary makes it clear where to add a new capability: new failure pattern → `classifier.py`; new repair strategy → `repair.py`; new provenance field → `planner.py` and `artifact_store.py`.
- `runner.py` becomes the only module that knows the full healing sequence. It is thin — no business logic, only sequencing.

### Alternatives Rejected

- **Keep god module, add tests:** The test surface is the full 600-line module — every test must mock everything.
- **2-module split (classifier + healer):** Still leaves planner, repair, and verifier mixed — the most complex code stays in one place.

### Consequences

- **Positive:** 556 unit tests, with test files per module. Adding a repair strategy requires touching `repair.py` and `ast_repair.js` only. Architecture matches the documentation.
- **Negative:** One additional import hop — callers import from `src.healing.runner`, not `src.agents.healer`. Old import paths were updated across the codebase.
- **Revisit trigger:** None planned.
- **Revisit trigger:** A third provider with a non-OpenAI-compatible API.
