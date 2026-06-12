# Historical Documents

> These documents are preserved for reference but are no longer active.
> They describe engineering decisions, evaluations, and plans from the 11-phase
> Modernization Program (completed 2026-06-06).
>
> **Do not update these documents.** If you need to record new decisions or plans,
> use the active documentation in `docs/`.

---

## Contents

| File | What it contains | Why archived |
| --- | --- | --- |
| `architecture-review.md` | Phase 0 audit of the pre-modernization codebase | All findings resolved. Pre-modernization architecture no longer exists. |
| `modernization-plan.md` | 11-phase modernization plan with deliverables and estimates | All 11 phases complete. The plan served its purpose. |
| `progress.md` | Phase-by-phase implementation history (Phases 0–11) | Engineering history. No contributor-facing value now that the program is complete. |
| `documentation-audit.md` | Phase D1 audit of documentation accuracy | Internal process document. Audit is complete. |
| `ast-evaluation.md` | Tool comparison: ts-morph vs Babel vs tree-sitter vs SWC | Decision recorded in ADR-003. The evaluation document retains research value. |
| `observability-evaluation.md` | Tool comparison: OTEL vs Langfuse vs custom JSONL tracer | Decision recorded in ADR-004. The evaluation document retains research value. |
| `technical-debt.md` | 15-item technical debt register from the modernization program | All 15 items resolved. Debt is fully retired. |
| `phase-12-documentation-modernization.md` | Phase 12 execution log — documentation governance & cleanup | Phase complete. |
| `phase-13-quality-gates-modernization.md` | Phase 13 execution log — GitHub Actions CI & pytest | Phase complete. |
| `phase-14-repository-rationalization.md` | Phase 14 execution log — dead code removal & legacy cleanup | Phase complete. |
| `phase-15-experience-consistency.md` | Phase 15 execution log — phase-ref cleanup, gitignore, smoke test, example hardening | Phase complete. |
| `phase-16-ui-audit.md` | Phase 16 audit of the workbench UI against the post-modernization architecture | Audit findings fully addressed in Phase 17. |
| `phase-17-workbench-redesign.md` | Phase 17 plan and execution log — Overview tab, unified artifacts, Evaluation workspace, observability activation, Models tab | Phase complete. |
| `phase-18-documentation-audit.md` | Phase 18 documentation reality audit — full inventory, wrong facts, gaps, modernization plan | Audit complete. All fixes applied. |

---

## Context

The Modernization Program ran from 2026-06-06 and transformed this project from a
prototype (maturity score 27/100) to a reference AI Systems Engineering project
(82/100) across 11 phases covering structured outputs, LLM layer modernization,
architecture cleanup, healer decomposition, AST repair, context collection,
evaluation framework, observability, explainability, UI reposition, and
documentation modernization.

The active documentation is in `docs/` (architecture, development, evaluation,
prompts), `README.md`, and `docs/decisions.md`.
