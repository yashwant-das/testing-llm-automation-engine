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
- **attrs:** Validation via validators, but no JSON schema generation, less OpenAI tool\_call integration.
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

Full evaluation recorded in `docs/ast-evaluation.md`.

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
**Status:** UNDER INVESTIGATION

### Context

No observability exists. Token usage, latency, retry counts, and failure patterns are invisible. Running a healing session produces JSON artifacts but no queryable traces.

### Decision

Pending evaluation. Candidates: OpenTelemetry + Jaeger/OTLP, Langfuse (self-hosted), stdout OTEL exporter.

### Evaluation Criteria

- Local-first (no cloud dependency required)
- Python SDK maturity
- LLM-specific signals (token count, model name, prompt version)
- Developer ergonomics for a single-engineer project

### Preliminary Assessment

- **OpenTelemetry (stdout exporter):** Zero dependency, always available, queryable with jq. No UI but maximum portability.
- **Langfuse (self-hosted):** LLM-native traces with prompt/completion view, cost tracking, evaluation UI. Requires Docker.
- **Langfuse (cloud):** Same features, no Docker, but data leaves the machine. Acceptable for non-sensitive workloads.

Preliminary recommendation: **Start with OpenTelemetry stdout exporter** as zero-dependency baseline; add Langfuse as optional enhancement once the instrumentation layer is in place.

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
- **Negative:** File I/O on every call (mitigated by caching in prompt\_loader).
- **Action Required:** Add `prompts/manifest.json` with version and hash fields. Update `prompt_loader.py` to expose version metadata.

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
