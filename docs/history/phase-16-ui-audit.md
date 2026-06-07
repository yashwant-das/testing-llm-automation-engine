# UI Audit — AI Engineering Workbench (Phase 16)

> Audit-only assessment of the current user experience against the architecture
> that exists after Phases 1–15. No redesign, no new features, no implementation.
> Every finding below is grounded in repository evidence (file:line).
>
> Date: 2026-06-07 · Scope: `src/app.py`, `src/services/`, `schemas/`, generated
> artifacts, traces, benchmark surfaces, and the docs that describe them.

---

## Executive Summary

The backend modernization (Phases 1–15) is real and high quality: structured
Pydantic contracts, a decomposed healing pipeline, AST repair, context collection,
an evaluation framework, an observability tracer, and rich explainability metadata
all exist in the codebase. **The user interface has not caught up.** It still
presents the system the way the original prototype did — as a three-workflow demo
("Generate / Heal / Vision") with three read-only inspectors bolted on.

The single most serious finding is that **the observability layer is never
activated in the running application.** `configure_tracer()` is called nowhere
except inside a docstring example ([`src/observability/__init__.py:11`](../src/observability/__init__.py)).
The global tracer is therefore always `NullTracer`, every span-recording call is a
silent no-op, `logs/traces.jsonl` is never written, and the **Trace Inspector tab
is permanently empty**. Meanwhile `README.md`, `docs/architecture/overview.md`, and
`docs/development/debugging.md` all state as fact that "every LLM call is recorded
in `logs/traces.jsonl`." This is the textbook architecture-says-one-thing,
implementation-does-another gap, and it directly undermines the project's central
claim of being an _observable_ AI system.

The second theme is **asymmetry**: healing is a first-class, fully-instrumented,
fully-explainable workflow, while generation and vision are essentially
fire-and-forget. They produce no artifact, carry no provenance, surface none of
the rich context they collect, and write no traces.

The third theme is **hidden capability**: the evaluation framework has three
benchmark runners, a mutation engine, and a model registry, but the UI exposes
exactly one deterministic heuristic benchmark with no persistence, no history, and
no comparison — none of the "compare models / track regressions" workflows the
evaluation docs describe.

**Verdict to the core question** — _if a senior SDET/AI-systems engineer opened
this today, would they trust it, inspect it, and understand the architecture from
the UI alone?_ **Not yet.** They would see a competent demo with one genuinely
excellent surface (the healing decision artifact) surrounded by empty or shallow
panels that contradict the documentation.

---

## Current State Assessment

### What exists today

The UI is a single Gradio `Blocks` app ([`src/app.py`](../src/app.py)) with six tabs
in one flat row:

| #   | Tab                 | Backing service                                  | Nature                          |
| --- | ------------------- | ------------------------------------------------ | ------------------------------- |
| 1   | Generation Pipeline | `generation_service.py`                          | Producer (LLM + browser)        |
| 2   | Healing Pipeline    | `healing_service.py`                             | Producer (LLM + browser + AST)  |
| 3   | Vision Pipeline     | `vision_service.py`                              | Producer (vision LLM + browser) |
| 4   | Artifact Inspector  | `workbench_service.list_artifacts/load_artifact` | Consumer (read-only)            |
| 5   | Benchmark Explorer  | `workbench_service.run_classification_benchmark` | Tool (deterministic)            |
| 6   | Trace Inspector     | `workbench_service.load_traces`                  | Consumer (read-only)            |

The header is a single line of markdown ([`src/app.py:90-94`](../src/app.py)):
"AI Testing Workbench" + "Reference implementation: structured LLM outputs ·
evaluation · observability · AST-based repair · explainability". There is no
landing page, no architecture view, no navigation guidance. The app opens directly
on the Generation tab.

The clean part: `app.py` is wiring only; all logic lives behind the service layer
(ADR-006 holds). Streaming generators map to Gradio `yield`, giving live progress
timelines. The Artifact Inspector pairs a rendered markdown report with a raw-JSON
panel. These are good bones.

---

## Strengths

These are working well and should be **preserved** through any future redesign:

1. **The healing decision artifact is genuinely excellent.**
   [`HealingDecision.to_markdown()`](../schemas/healing.py) renders diagnosis, root
   cause evidence, confidence _and a confidence rationale_, reasoning steps, a
   before/after code diff, and a full provenance block (model, prompt version +
   hash, execution time, context-snapshot id). This is exactly what an engineer
   needs to validate a repair. It is the high-water mark the rest of the UI should
   be measured against.

2. **Artifact Inspector dual view** (rendered markdown + raw JSON,
   [`src/app.py:257-292`](../src/app.py)) is the right pattern: human-readable plus
   machine-truth in one place.

3. **Service-layer boundary is honest.** The UI imports only from `src/services/`;
   no pipeline logic leaked into `app.py`. This makes a redesign low-risk.

4. **Streaming progress timelines** give immediate feedback during long LLM/browser
   operations — the right interaction model for this kind of tool.

5. **The heuristic classification benchmark is honest and deterministic**
   ([`workbench_service.py:96-172`](../src/services/workbench_service.py)): no LLM,
   runs in milliseconds, shows per-case expected-vs-classified with confidence. It
   cannot be gamed and it tells the truth.

6. **Pydantic contracts everywhere** mean the data the UI _could_ show is already
   structured and validated — the redesign is a surfacing problem, not a data
   problem.

---

## UX Debt (surfaces still reflecting the prototype)

1. **Prototype-era timeline copy.** The streaming timelines are written as a demo
   narration, not engineering diagnostics — heavy emoji per line and marketing
   verbs: "Pre-heating headless runner", "Compressing image bytes to base64"
   ([`vision_service.py:71,108`](../src/services/vision_service.py)), "Synthesizing
   failure classification and resolution strategy", "Engineering script structure
   and selectors" ([`generation_service.py:64`](../src/services/generation_service.py)).
   This reads as a product demo, not an SDET tool.

2. **Misleading repair label (correctness bug in reporting).** The healing timeline
   hardcodes "**Repair Applied**: Selector replaced" and the timeline step
   "SelectorUpdated" **regardless of the actual repair strategy**
   ([`healing_service.py:241,245`](../src/services/healing_service.py)). When the
   repair is `import_add`, `timeout_adjust`, `assertion_swap`, or `role_argument`,
   the UI still says a selector was replaced. This is a literal leftover from when
   selector replacement was the only repair, and it actively misinforms the user.

3. **Confidence shown louder than outcome.** The timeline foregrounds
   `AI Hypothesis ... (Confidence: 95%)` mid-run
   ([`healing_service.py`](../src/services/healing_service.py)) even on runs that
   subsequently fail verification. The artifact report handles this correctly
   (Status ❌ alongside confidence), but the live timeline can leave a
   "95% confident" impression on a failed heal.

4. **Three names for one product.** "AI Testing Workbench"
   ([`app.py:2,89,90`](../src/app.py), `README.md:1`), "Testing LLM Automation
   Engine" (`docs/env-variables.md:3`, `docs/docker.md:3`), and "AI Engineering
   Workbench" ([`workbench_service.py:2`](../src/services/workbench_service.py) and
   this phase's own title). A workbench that can't name itself consistently does
   not feel like one coherent system.

5. **Inconsistent demo defaults.** Generation defaults to
   `the-internet.herokuapp.com/login`; Vision defaults to `saucedemo.com`
   ([`app.py:104,206`](../src/app.py)). Generation Run-Test timeout is 45s
   ([`generation_service.py`](../src/services/generation_service.py)) while healing
   uses 60s. Small, but they betray independent prototype origins rather than a
   designed whole.

---

## Information Architecture Issues

1. **Two mental models flattened into one row.** Tabs 1–3 are _producers_
   (workflows that do AI work) and tabs 4–6 are _consumers/tools_ (inspect what was
   produced). They sit in a single undifferentiated `gr.Tabs` row
   ([`app.py:96`](../src/app.py)) with no grouping, so the relationship
   "run a pipeline → inspect its artifact/trace" is invisible. A user has no cue
   that the Artifact and Trace inspectors are _downstream of_ the Healing tab.

2. **No entry point / no architecture view.** The app opens on Generation with a
   one-line header. There is nowhere in the UI that explains what the system is,
   how the pipeline stages connect, or where to look for what. The audit's question
   "understand the architecture from the UI alone?" fails immediately — all that
   knowledge lives in `docs/` and never reaches the running app.

3. **Naming mixes metaphors.** "Pipeline" (×3), "Inspector" (×2), "Explorer" (×1).
   "Benchmark Explorer" is actually a single-button _runner_, not an explorer —
   there is nothing to explore (no dataset browse, no run history).

4. **Discoverability of evidence is poor.** After a healing run, the decision is
   _also_ shown inline in the Healing tab's "Decision Report" sub-tab, _and_
   separately in the Artifact Inspector. The relationship between "the report I just
   saw" and "the artifact list" is never made explicit; the user must infer it.

---

## Visibility Gaps (capabilities that exist but are hidden)

1. **Observability is invisible because it is inert.** (See Trust Assessment.)
   `configure_tracer()` is never invoked in `app.py`, the services, the healer CLI,
   or the benchmarks — only in a docstring
   ([`src/observability/__init__.py:11`](../src/observability/__init__.py)). The
   full `Tracer` implementation ([`tracer.py`](../src/observability/tracer.py)) —
   session aggregation, token totals, LLM spans, subprocess spans — runs for nobody.
   The Trace Inspector renders "_No trace file found … Run a healing session to
   generate traces._" forever ([`workbench_service.py:191`](../src/services/workbench_service.py)),
   and running a healing session does **not** change that.

2. **Generation collects rich context and shows none of it.**
   [`generator.py`](../src/agents/generator.py) builds a full `ContextSnapshot` —
   DOM, accessibility tree, locator candidates, console errors — and feeds it to the
   model, then returns only the code string. The UI's timeline brags about
   "capturing DOM layout" but the user never sees the DOM, the a11y tree, or the
   candidate locators the model was actually given. _"Would they understand what the
   model saw?"_ — No, for generation.

3. **Execution-timeline artifacts are orphaned.** Every heal writes both
   `healing_decision_*.json` and `execution_timeline_*.json`
   ([`artifact_store.py:38`](../src/healing/artifact_store.py)), but the Artifact
   Inspector lists only `healing_decision_*.json`
   ([`workbench_service.py:48`](../src/services/workbench_service.py)). Half the
   artifacts written to disk are unreachable from the UI.

4. **Model registry is hidden.** `ModelRegistry` / `ModelCapabilities`
   ([`registry.py`](../src/llm/registry.py)) hold provider, vision-capability, and
   context-window metadata — never surfaced. The user cannot see which model is
   active, its capabilities, or the fallback chain.

5. **Vision evidence is shallow.** The screenshot is shown (good), but the vision
   tab never surfaces what the model concluded _about_ the screenshot beyond the
   final code — no extracted elements, no reasoning, no provenance.

---

## Workflow Gaps (engineering tasks the UI can't support)

1. **Investigate a failure end-to-end.** A user can run a heal and read one
   decision, but cannot trace token usage / latency / retries (tracer inert),
   cannot see the execution timeline (orphaned), and cannot correlate the decision
   to its LLM spans (no spans). The investigation trail dead-ends.

2. **Compare models.** `docs/evaluation/model-comparison.md` documents a whole
   methodology, but the UI has no way to run a benchmark against two models, or even
   to _select_ a model. Provider/model selection is `.env`-only.

3. **Compare prompts / track regressions.** `BenchmarkRun.save_report()` exists
   ([`evaluation.py`](../schemas/evaluation.py)) and `benchmarks/reports/` is the
   intended home, but the Benchmark Explorer never persists a run
   ([`workbench_service.py:128`](../src/services/workbench_service.py) builds a run
   and drops it), so `benchmarks/reports/` is empty and there is no history to
   compare. No regression view exists.

4. **Run the LLM-backed benchmarks.** Generation and intent-validation runners
   exist (`benchmarks/generation/runner.py`, `benchmarks/intent_validation/runner.py`)
   but are unreachable from the UI; only the no-LLM heuristic classifier is wired up
   ([`app.py:294-310`](../src/app.py)). The most decision-relevant evaluations
   (does the model actually generate good tests?) are CLI-only.

5. **Understand context collection.** The context subsystem is a headline feature
   of the architecture, yet no UI surface lets a user inspect a `ContextSnapshot`
   for a URL.

6. **Generation/vision review loop.** Because generation produces no artifact and no
   provenance, there is no way to come back later and audit _why_ a generated test
   looks the way it does, or which model/prompt produced it.

---

## Outdated Concepts

1. **"Selector replaced" as the universal repair verb** — predates the six-strategy
   AST repair system; now factually wrong for five of six strategies
   ([`healing_service.py:241`](../src/services/healing_service.py)).

2. **Demo-narration timelines** — predate the idea of the system as an engineering
   tool. They describe _theatre_ ("pre-heating", "synthesizing") rather than
   _state_ ("collecting DOM: 1240 nodes", "classifier: TIMEOUT @ 0.92").

3. **"AI Testing Workbench" title** — predates the Phase 10 repositioning to "AI
   Engineering Workbench" that `workbench_service.py` and the modernization record
   already adopted.

4. **Documentation that describes a working tracer** — `README.md:69,312,333`,
   `docs/architecture/overview.md:10`, and `docs/development/debugging.md`
   (Failure Mode 5 even tells users to call `configure_tracer()` themselves, tacitly
   admitting the app doesn't) describe an observability story the running app does
   not deliver.

5. **Empty `benchmarks/reports/`** — the directory and `save_report()` plumbing
   anticipate a run-history workflow that the UI never triggers.

---

## Engineering Trust Assessment

**Can engineers trust what they see? Partially — and the gaps are the kind that
erode trust fastest.**

- **What earns trust:** The healing decision artifact. It shows its work — evidence,
  rationale, provenance, and the actual diff. An engineer can read it and decide
  whether the repair is sound. This one surface is genuinely workbench-grade.

- **What breaks trust:**
  - **The empty Trace Inspector that the docs say should be full.** An engineer who
    reads the README ("every LLM call is recorded"), runs a heal, opens the Trace
    Inspector, and sees "_No trace file found_" will conclude either the tool is
    broken or the docs lie. Both conclusions are corrosive, and both are currently
    correct. This is the highest-severity trust issue in the system.
  - **The "Selector replaced" mislabel.** Once an engineer notices the UI claims a
    selector was swapped when actually an import was added, they stop trusting the
    timeline narration entirely.
  - **Confidence theatre.** A prominent "95% confident" on a run that then fails
    verification reads as a system that doesn't know its own accuracy.
  - **Invisible model/provenance in generation.** A generated test with no record of
    which model/prompt/context produced it is not auditable, and unauditable output
    is untrusted output in a test-engineering context.

Net: trust is **high for healing artifacts, low everywhere else**, and actively
_negative_ for observability because the product over-claims it.

---

## Workbench Opportunities

Capabilities the architecture already supports that a true workbench would expose
(for Phase 17 consideration — **not** to build now):

1. **Activate and surface observability** — the single highest-leverage change.
   Turn on the tracer, then make every run link to its session span (tokens,
   latency, retries, subprocess exit codes). The data model already exists.
2. **Unify provenance across all three pipelines** — give generation and vision the
   same artifact/provenance treatment healing already has.
3. **A context inspector** — let users see the `ContextSnapshot` (DOM, a11y tree,
   locator candidates) the model was given, for both generation and healing.
4. **A real evaluation surface** — run any of the three benchmarks against a
   selectable model, persist runs to `benchmarks/reports/`, and show run-over-run
   comparison and regression deltas.
5. **A model panel** — surface `ModelRegistry` so the active model, its
   capabilities, and the fallback chain are visible.
6. **An overview / architecture landing surface** — make the pipeline topology
   legible from inside the app.
7. **Run history** — a unified list of recent runs (any pipeline) that links to
   each run's artifact + trace, making "investigate a failure" a first-class flow.

---

## Recommendations

Prioritized. Severity reflects impact on trust and on the "is this an engineering
workbench?" question — not implementation effort.

### Critical

- **C1. Resolve the observability contradiction.** Either activate the tracer in the
  app/CLI entrypoints so traces are actually produced, _or_ (if intentionally
  deferred) stop the docs and UI from claiming observability works. The current
  state — fully built, never run, loudly documented — is the worst of all options.
  Evidence: [`observability/__init__.py:11`](../src/observability/__init__.py),
  `README.md:69/312/333`, [`workbench_service.py:191`](../src/services/workbench_service.py).
- **C2. Fix the misleading repair label.** "Selector replaced" / "SelectorUpdated"
  must reflect the actual `repair_strategy`. Reporting that misstates what happened
  is a correctness defect, not a cosmetic one.
  Evidence: [`healing_service.py:241,245`](../src/services/healing_service.py).

### High

- **H1. Settle the product name** to one (the modernization intent is "AI
  Engineering Workbench") and apply it across `app.py`, `README.md`, and docs.
- **H2. Give generation and vision provenance + artifacts** on par with healing
  (model, prompt version/hash, tokens, context id, timestamp). Today
  `GenerationResult` carries only `code` ([`schemas/generation.py`](../schemas/generation.py)).
- **H3. Surface the context the model saw** for generation/vision (and in the
  healing evidence panel) — DOM / a11y tree / locator candidates.
- **H4. Expose a real evaluation workflow** — at minimum persist benchmark runs and
  show history; ideally make all three runners reachable with a model selector.

### Medium

- **M1. Reorganize IA** into producers vs. inspectors, with an overview/landing
  surface that explains the pipeline topology.
- **M2. Surface the orphaned execution-timeline artifacts**, or stop writing them.
- **M3. Rewrite timeline copy** from demo narration to engineering state (counts,
  classifier output, strategy chosen, exit codes). Reduce decorative emoji.
- **M4. Show the active model / registry** somewhere in the UI.

### Low

- **L1. Align demo defaults and timeouts** across tabs.
- **L2. Rename "Benchmark Explorer"** to match what it does (a runner) — or make it
  an actual explorer.
- **L3. Clarify the live "confidence" presentation** so it never outshines the
  verification outcome.

---

## Future State Vision

After a future redesign, opening the workbench should feel like opening an
**engineering console for an AI test system**, not a demo of three tricks.

A user lands on an **overview** that shows the pipeline topology and recent activity
— a list of runs across all three pipelines, each one click away from its full
provenance. Running any pipeline produces a **first-class artifact** with the same
shape regardless of type: what was asked, what context the model was given, which
model and prompt (version + hash) answered, what it produced, how many tokens and
how long it took, how many retries, and — for healing — the diagnosis, the repair
strategy actually used, and the verification result.

**Observability is real and omnipresent:** every run links to its trace; token,
latency, and retry data are one click away; nothing in the UI claims a capability
the system doesn't deliver. **Evaluation is a workspace, not a button:** pick a
model, run a benchmark, see it persisted next to previous runs, and read the
regression delta. **Context is inspectable:** the DOM, accessibility tree, and
locator candidates the model saw are always available, so a skeptical engineer can
verify the model wasn't handed the answer.

The healing decision artifact — already excellent — becomes the _template_ for the
whole experience rather than the one good room in the house. The language
throughout reads like instrumentation, not marketing. And the system names itself
the same thing everywhere.

When a senior SDET or AI-systems engineer opens it, the answer to every question in
this audit's core list is **yes** — and it is yes _because of what the UI shows_,
not because they read the docs.

---

_End of audit. No implementation performed in this phase. This document is the
input to a future Phase 17 redesign._
