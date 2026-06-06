# Documentation Audit — Phase D1

> Completed: 2026-06-06 as part of Phase 11 — Documentation Modernization.
> Purpose: catalogue every document's accuracy before rewriting.

---

## Audit Summary

| Document | Status | Action |
| --- | --- | --- |
| `README.md` | Stale — describes pre-modernization architecture | Full rewrite |
| `docs/architecture-review.md` | Accurate — historical audit record, keep as-is | Preserve |
| `docs/modernization-plan.md` | Accurate — living plan, complete through Phase 10 | Preserve |
| `docs/progress.md` | Accurate — updated per phase | Preserve |
| `docs/decisions.md` | Partially stale — ADR-005 "Action Required" now done; missing ADRs for context collection, evaluation design, thread-local isolation | Update |
| `docs/technical-debt.md` | Stale — all items marked OPEN, all resolved through Phase 9 | Update statuses |
| `docs/scorecard.md` | Stale — only baseline score (27/100); no post-Phase updates | Update |
| `docs/ARCHITECTURE.md` | Stale — describes pre-Phase 3 monolithic app.py | Replace with `docs/architecture/` |
| `docs/DEMO_GUIDE.md` | Stale — references old 3-tab UI; old agent invocation paths | Delete |
| `docs/HEALING_SCENARIOS.md` | Partially valid — scenarios still work, but references old file paths and lacks Phase 9 explainability context | Supersede with `docs/architecture/healing.md` |
| `docs/ast-evaluation.md` | Accurate — tool comparison is valid and implemented | Preserve |
| `docs/observability-evaluation.md` | Accurate — tool comparison is valid and implemented | Preserve |
| `docs/backlog.md` | Accurate | Preserve |
| `benchmarks/datasets/README.md` | Accurate | Preserve |

**Net change:** 3 new directory trees created (`docs/architecture/`, `docs/evaluation/`, `docs/prompts/`, `docs/development/`). README fully rewritten. 2 stale documents deleted. `docs/decisions.md`, `docs/technical-debt.md`, and `docs/scorecard.md` updated.

---

## Per-Document Findings

### README.md — STALE

**Outdated content:**

- Project structure diagram references `src/agents/`, `src/models/` (old structure). Actual structure has `src/services/`, `src/healing/`, `src/context/`, `src/llm/`, `src/observability/`, `schemas/`, `benchmarks/`.
- Describes 3 UI tabs: "Test Generator", "Vision Agent", "Self-Healer". Actual UI has 6 tabs: "Generation Pipeline", "Healing Pipeline", "Vision Pipeline", "Artifact Inspector", "Benchmark Explorer", "Trace Inspector".
- Agent invocation: `uv run python -m src.agents.healer` — `src/agents/healer.py` is now a compatibility shim; the canonical invocation is through the service layer.
- References `docs/ARCHITECTURE.md`, `docs/DEMO_GUIDE.md`, `docs/HEALING_SCENARIOS.md` — all stale paths.
- References `ENV_VARIABLES.md`, `DOCKER.md`, `AGENTS.md` — undiscovered files, not verified as current.
- No mention of: LLMRouter, Pydantic schemas, AST repair, context collection, evaluation framework, observability, explainability, benchmarks.
- Title says "Testing LLM Automation Engine" — UI now says "AI Testing Workbench".
- "Key Differentiators" section uses SaaS/marketing language ("What sets this framework apart").

**Missing content:**

- Architecture overview with diagram
- Evaluation system / benchmarks
- Observability / trace inspection
- Explainability / HealingDecision provenance
- Repository structure (accurate)
- Technology choices and rationale
- How to add a model / benchmark / strategy

**Action:** Full rewrite.

---

### docs/decisions.md — PARTIALLY STALE

**Outdated content:**

- ADR-005 "Action Required" note: "Add `prompts/manifest.json`" — done in Phase 9.
- All ADRs have no "Resolved in Phase N" annotation.

**Missing ADRs:**

- Context collection architecture (Phase 6): single browser session, why not per-collector sessions.
- Evaluation framework design (Phase 7): pure functions, classification-only default, injectable healer_fn.
- Thread-local session isolation for Gradio (Phase 8): why `threading.local()` over async.
- Healer decomposition (Phase 4): why 7 single-responsibility modules over a simpler refactor.

**Action:** Update ADR-005 status; add 4 missing ADRs.

---

### docs/technical-debt.md — STALE

**Status fields:**

All 15 items are marked `OPEN`. All have been resolved through Phase 9:

| Item | Resolved in |
| --- | --- |
| TD-001 UI god module | Phase 3 |
| TD-002 Fragile parsing | Phase 1 |
| TD-003 String repair | Phase 5 |
| TD-004 No evaluation | Phase 7 |
| TD-005 No observability | Phase 8 |
| TD-006 Dataclasses | Phase 1 |
| TD-007 HTML-only context | Phase 6 |
| TD-008 Module-level singleton | Phase 2 |
| TD-009 No retry/fallback | Phase 2 |
| TD-010 No model registry | Phase 2 |
| TD-011 No prompt versioning | Phase 9 |
| TD-012 Evidence staleness | Phase 6 |
| TD-013 Dead code | Phase 1 |
| TD-014 Vision duplication | Phase 3 |
| TD-015 TestRunResult mock | Phase 1 |

**Action:** Mark all resolved with phase reference. Update "Resolved" section.

---

### docs/scorecard.md — STALE

**Score history table** has only the baseline (27/100). The expected post-phase scores were listed in a target table but never updated with actuals.

**Action:** Add post-Phase 10 score estimate row.

---

### docs/ARCHITECTURE.md — STALE

Describes the old monolithic `app.py` with "Monitor → Investigate → Reason → Act → Report" framing that no longer matches the actual pipeline structure. References `src/agents/healer.py` as the primary entry point.

**Action:** Delete. Replace with `docs/architecture/` directory tree.

---

### docs/DEMO_GUIDE.md — STALE

References old 3-tab UI, old tab names, old agent invocation commands.

**Action:** Delete.

---

### docs/HEALING_SCENARIOS.md — PARTIALLY VALID

Healing scenarios (Locator Drift, Timeout, Assertion Failure) are still accurate at the scenario level. But: references old `src/agents/healer.py` paths, misses Phase 9 provenance fields in artifacts, misses context collection from Phase 6, misses AST repair from Phase 5.

**Action:** Supersede with `docs/architecture/healing.md` which covers the same scenarios with accurate implementation references.
