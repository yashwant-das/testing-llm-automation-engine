# Phase 17 — AI Engineering Workbench Redesign (Plan)

> Driven directly by [`docs/ui-audit.md`](../docs/ui-audit.md) (Phase 16).
> This document is both the plan and the living execution tracker.
> Status legend: ☐ not started · ◐ in progress · ☑ done.
>
> Date opened: 2026-06-07 · Predecessor: Phase 16 (audit-only).

---

## Thesis

Phase 16 proved the backend modernization is real but the UI still presents the
system as a three-trick demo with empty/contradictory panels. Phase 17 makes the
**experience tell the same story the architecture already tells**:

> Every pipeline run — generation, healing, vision — becomes a first-class,
> **traced**, **provenance-bearing** Run that produces a uniform artifact,
> browsable in one place, with a real overview and a real evaluation workspace.

The healing decision artifact ([`HealingDecision.to_markdown()`](../schemas/healing.py))
is already workbench-grade. Phase 17 does not invent a new bar — it **generalizes
that bar to every surface**.

This is a surfacing-and-truth phase, not a new-capability phase. We add no AI
capability the architecture does not already support (the audit's own constraint).
We prefer **removal over addition**, **clarity over visual complexity**, and
**engineering language over marketing**.

---

## ⚠️ Key decision (resolve before Stage 1 code)

**Audit C1 is an explicit fork: _activate_ observability or _remove the claim_.**

This plan assumes **ACTIVATE**. Rationale:

- The project's stated identity is a _reference observable AI Systems Engineering
  project_. Observability is a named pillar (README, `ai-systems-engineering.md`).
  Removing it guts the thesis.
- The `Tracer` / `TraceWriter` / span schemas are fully built and good quality
  ([`src/observability/`](../src/observability/)). Activation is low-risk wiring,
  not new construction. The cost is small; the trust payoff is the single largest
  in the audit.
- Removing would mean deleting working code _and_ rewriting README + architecture +
  debugging docs to walk back a central claim — more work, less value.

**If you prefer REMOVE instead:** Stage 1 inverts — delete the observability layer,
the Trace Inspector tab, and all trace claims from README/architecture/debugging
docs; Stages 2–5 drop every "link to trace" element. Say so and the plan adjusts.

Everything below assumes ACTIVATE.

---

## Constraints (carried from project ethos + audit)

1. No new AI capabilities, providers, or repair strategies. Surfacing only.
2. Preserve the service-layer boundary — `app.py` stays wiring-only (ADR-006).
3. Prefer removal: consolidate duplication, cut emoji theatre, delete false claims.
4. Every UI claim must be true at runtime. No surface may describe a capability the
   running app does not deliver.
5. Keep the 440 unit tests green; add tests for every new contract.
6. Stay on Gradio (ADR-006 + the clean service boundary make a framework swap
   unjustified; the audit did not call for one).

---

## Workstream → audit-recommendation map

| Stage                              | Closes (audit IDs)       | Theme                             |
| ---------------------------------- | ------------------------ | --------------------------------- |
| Stage 1 — Truth & language         | C1, C2, H1, M3, L1, L3   | Stop misinforming the user        |
| Stage 2 — Provenance backbone      | H2, + healing-loop dedup | One artifact shape for every run  |
| Stage 3 — Visibility               | H3, M2, M4               | Surface what the model saw & used |
| Stage 4 — Evaluation workspace     | H4, L2                   | Run, persist, compare             |
| Stage 5 — Information architecture | M1, IA-1..4              | Overview, grouping, run history   |

Sequencing rationale: fix the lies first (cheapest, highest trust). Build the
provenance/trace **data backbone** next (everything downstream surfaces it). Then
surface it, then evaluate over it, then reorganize the navigation around it last —
reorganizing surfaces that don't exist yet would be wasted motion.

---

## Stage 1 — Truth & language

Goal: nothing in the running app or its docs is false. Cheapest, highest-trust.

### 1a. Activate observability (C1)

- ☑ Call `configure_tracer()` at app startup — added to [`src/app.py`](../src/app.py)
  at module level (before service imports), so the global tracer is a real `Tracer`.
- ☑ Activate the **CLI healing path** — `configure_tracer()` added to the
  `__main__` block in [`src/agents/healer.py`](../src/agents/healer.py).
- ☑ **Session-aware CLI** — `attempt_healing` in
  [`src/healing/__init__.py`](../src/healing/__init__.py) now calls
  `get_tracer().start_session()` / `end_session()` in a try/finally, matching
  `heal_test_streaming`'s session management. Both paths now produce tracer spans.
  Full loop extraction deferred to backlog (streaming vs synchronous interface
  makes a shared generator necessary; scoped as a future refactor).
- ☑ Tests added: `TestAttemptHealingTracerSession` asserts start/end session called
  for both success and file-not-found branches.
- ☑ Verify: run a heal → `logs/traces.jsonl` is written → Trace Inspector
  populates (it already renders correctly once the file exists,
  [`workbench_service.py:182`](../src/services/workbench_service.py)).

### 1b. Fix the misleading repair label (C2)

- ☑ Added `REPAIR_STRATEGY_LABELS` map to [`schemas/healing.py`](../schemas/healing.py)
  next to the `RepairStrategy` enum — single source of truth for UI and reports.
- ☑ `heal_test_streaming` ([`healing_service.py`](../src/services/healing_service.py))
  now uses `REPAIR_STRATEGY_LABELS` and logs "RepairApplied" (was "SelectorUpdated").
- ☑ `attempt_healing` ([`src/healing/__init__.py`](../src/healing/__init__.py))
  likewise uses the label map and logs "RepairApplied".
- ☑ Tests added: `TestRepairStrategyLabels` asserts all six strategies have labels
  and label count matches enum count.

### 1c. Settle the name (H1)

- ☑ Applied **"AI Engineering Workbench"** to:
  [`src/app.py`](../src/app.py) (module docstring, `gr.Blocks` title, `gr.Markdown`),
  `README.md:1`, `docs/ai-systems-engineering.md` (2 occurrences),
  `docs/architecture/overview.md`, `docs/env-variables.md`, `docs/docker.md`.
- ☑ `grep -r "AI Testing Workbench"` returns nothing outside `docs/history/`
  and `docs/ui-audit.md` (the audit document itself records the old name as a finding).

### 1d. Language pass (M3) + low-priority truth items (L1, L3)

- ☑ Rewrote streaming timelines from demo narration to engineering state.
  "Pre-heating", "compressing image bytes", "synthesizing" removed.
  Now: `classifier=LOCATOR_DRIFT confidence=87% strategy=selector_replace`,
  `Exit code 0 — test passed`, `verification passed — confidence=87%` etc.
  Files: [`generation_service.py`](../src/services/generation_service.py),
  [`healing_service.py`](../src/services/healing_service.py),
  [`vision_service.py`](../src/services/vision_service.py).
- ☑ Reduced emoji to `✅` / `❌` / `→` set. Removed 🧠 🛠️ 🟢 🔴 🖼️.
- ☑ L3: verification outcome and confidence now appear together on the same
  timeline line once known.
- ☑ L1: aligned run timeout to 60s in `generation_service.py` (was 45s).
- Acceptance met: a reviewer reading a timeline sees instrument readings, not a script.

---

## Stage 2 — Provenance backbone (the data spine)

Goal: every run, not just healing, produces a uniform, provenance-bearing artifact.
This is the foundation Stages 3–5 surface.

- ☐ Introduce a **shared provenance contract** (mixin or base model in
  [`schemas/`](../schemas/)): `model_used`, `provider`, `prompt_version`,
  `prompt_hash`, `input_tokens`, `output_tokens`, `latency_ms`, `retry_count`,
  `trace_id`, `context_snapshot_id`, `timestamp`. `HealingDecision` already has
  most of these — refactor it to consume the shared contract (no behavior change).
- ☐ **GenerationDecision** (H2): wrap `GenerationResult.code`
  ([`schemas/generation.py`](../schemas/generation.py)) with the provenance
  contract + the `ContextSnapshot` used + a `to_markdown()` mirroring
  `HealingDecision`'s structure. Generation service emits it to
  `tests/artifacts/` and starts/ends a tracer session.
- ☐ **VisionDecision** (H2): same shape, plus `screenshot_path`. Vision service
  emits + traces.
- ☐ Generalize [`artifact_store`](../src/healing/artifact_store.py) +
  [`list_artifacts`](../src/services/workbench_service.py) to write/list **all**
  decision types (heal / generation / vision), not just `healing_decision_*`.
- ☐ Store `trace_id` on every artifact so an artifact can deep-link to its trace
  (realizes the "investigate end-to-end" workflow, audit Workflow Gap 1).
- Acceptance: running generation or vision writes a browsable artifact carrying
  which model/prompt/tokens/context produced it; unit tests cover each new
  `to_markdown()` and the round-trip load. Generation output becomes auditable
  (closes audit Trust point 4 and Workflow Gap 6).

---

## Stage 3 — Visibility

Goal: surface the backbone — show what the model saw and used.

- ☐ **Context inspector (H3):** render the `ContextSnapshot` (DOM excerpt, a11y
  tree, locator candidates, console errors) for generation, vision, and in the
  healing evidence panel. The data is already collected
  ([`src/agents/generator.py`](../src/agents/generator.py),
  [`schemas/artifacts.py`](../schemas/artifacts.py)); this is pure surfacing.
  Lets a skeptic verify the model "wasn't handed the answer."
- ☐ **Execution timelines (M2):** the orphaned `execution_timeline_*.json`
  ([`artifact_store.py:38`](../src/healing/artifact_store.py)) become visible inside
  the unified artifact view (paired with the decision they belong to). If we decide
  they add no value, **stop writing them** instead — explicitly one or the other,
  never written-but-hidden.
- ☐ **Model panel (M4):** surface [`ModelRegistry`](../src/llm/registry.py) — active
  model, provider, vision-capability, context window, and the fallback chain — as a
  small read-only panel.
- Acceptance: from any run's artifact a user can open the exact context the model
  received and see which model answered. No artifact written to disk is unreachable
  from the UI.

---

## Stage 4 — Evaluation workspace (L2 rename + H4)

Goal: turn the single-button "Benchmark Explorer" into a real evaluation surface.

- ☐ **Persist runs (H4):** `run_classification_benchmark`
  ([`workbench_service.py:128`](../src/services/workbench_service.py)) calls
  `BenchmarkRun.save_report()` → `benchmarks/reports/` (plumbing already exists,
  [`schemas/evaluation.py`](../schemas/evaluation.py)).
- ☐ **History + comparison (H4):** load prior reports and show run-over-run deltas
  (pass-rate, mean score, latency) — the regression view the eval docs describe but
  the UI never delivered.
- ☐ **Reach the LLM-backed runners (H4):** wire `benchmarks/generation/runner.py`
  and `benchmarks/intent_validation/runner.py` behind an LLM-availability guard
  (clear message when no model is reachable). Add a **model selector** (reads
  `ModelRegistry` / env) so "compare models" becomes possible.
- ☐ **Rename (L2):** "Benchmark Explorer" → "Evaluation" (it now actually explores).
- Acceptance: a user runs a benchmark, sees it saved next to previous runs with a
  delta, and can pick which model to evaluate. Closes audit Workflow Gaps 2–4.

---

## Stage 5 — Information architecture

Goal: reorganize navigation around the now-real backbone. Done last on purpose.

- ☐ **Group producers vs. engineering surfaces (M1 / IA-1):** separate the three
  Workflow tabs (Generation, Healing, Vision) from the Engineering surfaces
  (Run History, Evaluation, Traces, Models) — via grouped tabs or a left nav,
  within Gradio's constraints.
- ☐ **Overview / landing (IA-2):** a home surface stating what the system is, the
  pipeline topology (reuse the architecture diagram), and recent activity. The app
  should no longer open cold on a form.
- ☐ **Unified Run History (Opportunity 7):** one list of recent runs across all
  pipelines, each linking to its artifact **and** its trace. This is the spine that
  makes "investigate a failure" first-class.
- ☐ **Fold the inline healing "Decision Report" into the shared artifact view**
  (IA-4) so "the report I just saw" and "the artifact list" are the same object,
  not two unexplained copies.
- Acceptance: a first-time engineer can answer "what is this / where do I look /
  how do these stages connect" from inside the app, without `docs/`.

---

## Testing & verification strategy

- Unit tests (keep 440 green; add per new contract): shared provenance model,
  `GenerationDecision`/`VisionDecision` `to_markdown()` + round-trip, repair-label
  mapping (all six strategies), artifact-store generalization, benchmark
  persistence/history loader, healing-loop consolidation parity (CLI == UI core).
- Observability test: after a mocked session, assert spans are written and the
  Trace Inspector loader returns them.
- Gradio surfaces can't be fully unit-tested → manual verification via the `run`
  skill / launching the app for each new surface, plus screenshots in this doc.
- Gates stay green: `npm run lint` (eslint + ruff + markdownlint), `npm run test`
  (Playwright smoke), `uv run python -m pytest`.

---

## Risks & mitigations

- **Gradio ceiling for richer IA** (left nav / landing). Mitigate: stay within
  `Blocks`/`Tabs`/grouping; accept some layout constraint rather than a framework
  swap.
- **Healing-loop consolidation regressing the CLI.** Mitigate: parity tests before
  refactor; consolidate behind the existing public API (`attempt_healing` signature
  unchanged).
- **Scope creep.** Mitigate: every task traces to an audit ID; anything without one
  is out of scope for Phase 17.
- **Unbounded `traces.jsonl` growth** once observability is live. Out of scope to
  solve here; log a backlog item for retention/rotation.
- **Artifact volume** in `tests/artifacts/` once generation/vision also emit.
  Mitigate: confirm `.gitignore` covers them (it ignores `tests/artifacts/`); note
  a cleanup affordance as backlog.

---

## Explicitly out of scope

- New AI capabilities, new LLM providers, new repair strategies.
- Auth, multi-user, persistence beyond local files, deployment changes.
- Replacing Gradio.
- Trace/artifact retention policy (backlog).

---

## Success criteria (the audit's core questions, answered "yes" — by the UI)

- ☐ Understand how the system works — from the app (overview + topology).
- ☐ Trust it — every claim true at runtime; no empty panels the docs say are full.
- ☐ Inspect & validate decisions — uniform provenance-bearing artifacts for all
  three pipelines.
- ☐ Evaluate model quality & compare runs — real evaluation workspace with history.
- ☐ Investigate failures end-to-end — artifact ↔ trace ↔ timeline linked.
- ☐ Understand why a decision was made — context the model saw is inspectable.
- ☐ The system names itself one thing everywhere.

When every box is checked, the workbench _is_ what the architecture already claimed.

---

## Progress log

- 2026-06-07 — Plan drafted from Phase 16 audit. Awaiting decision on C1
  (activate vs. remove observability); plan assumes **activate**.
- 2026-06-07 — Stage 1 complete. 444 tests green (440 original + 4 new).
  `configure_tracer()` active in app + CLI. `REPAIR_STRATEGY_LABELS` added.
  Product name unified to "AI Engineering Workbench". Timeline language
  rewritten to engineering state across all three services.
