# Phase 12 — Documentation Governance, Cleanup & Modernization

> Started: 2026-06-06
> Status: IN PROGRESS

---

## Audit Findings

### Accurate (no changes needed)

| Document | Notes |
| --- | --- |
| `README.md` | Accurate post-Phase 11 rewrite |
| `ENV_VARIABLES.md` | Matches current env var implementation |
| `docs/decisions.md` | ADR-001 through ADR-011 present and accurate (references to eval files need path update after archival) |
| `docs/scorecard.md` | Post-Phase 10 and 11 scores accurate |
| `docs/technical-debt.md` | All 15 items resolved |
| `docs/ai-systems-engineering.md` | 9 patterns accurate against codebase |
| `docs/architecture/` (7 files) | All accurate |
| `docs/development/` (6 files) | All accurate |
| `docs/evaluation/` (5 files) | All accurate |
| `docs/prompts/` (4 files) | All accurate |
| `benchmarks/datasets/README.md` | Accurate format reference |
| `Dockerfile` | Accurate |

### Stale — needs update

| Document | Issue |
| --- | --- |
| `AGENTS.md` | References old `src/agents/`, `src/models/`, `src/utils/` structure. Instructs contributors to plug new features into `agents/`, `models/`, `utils/` — wrong. |
| `DOCKER.md` | References "Self-Healer" tab (renamed "Healing Pipeline"). Healer CLI example uses `src.agents.healer` (deprecated shim). |
| `docs/backlog.md` | All "Why deferred" reasons reference completed phases as prerequisites. "Deprecation Candidates" table partially resolved. |

### Historical / process — no active contributor value

| Document | Decision |
| --- | --- |
| `docs/architecture-review.md` | Phase 0 audit of pre-modernization codebase. Archive. |
| `docs/modernization-plan.md` | Completed 11-phase plan. "No New Feature Rule" checkboxes still `[ ]`. Archive. |
| `docs/progress.md` | 585-line phase-by-phase history. Archive. |
| `docs/documentation-audit.md` | Phase D1 internal process document. Archive. |
| `docs/ast-evaluation.md` | Pre-decision AST tool comparison. Conclusions in ADR-003. Archive. |
| `docs/observability-evaluation.md` | Pre-decision observability evaluation. Conclusions in ADR-004. Archive. |

### Structural issues

| Issue | Action |
| --- | --- |
| `src/tui/` — empty directory | Delete |
| `src/memory/` — empty directory | Delete |
| No documentation governance document | Create `docs/GOVERNANCE.md` |
| No `docs/history/` archive location | Create with README |

---

## Actions Completed

- [x] Audit all documentation files
- [x] Verify against actual codebase structure
- [x] Create `docs/history/` archive directory
- [x] Archive 6 historical process documents
- [x] Update `docs/decisions.md` ADR references to history paths
- [x] Rewrite `AGENTS.md` with accurate architecture
- [x] Update `DOCKER.md` — fix stale tab names and CLI invocation
- [x] Update `docs/backlog.md` — remove completed-phase prerequisites; update status of deprecation candidates
- [x] Create `docs/GOVERNANCE.md`
- [x] Delete empty `src/tui/` and `src/memory/` directories
- [x] Commit all changes

---

## Decisions Made

- **Archive, don't delete** historical planning/process documents. They record engineering decisions and effort that may have reference value. Archived to `docs/history/` where they are separated from active documentation.
- **Keep `docs/ast-evaluation.md` and `docs/observability-evaluation.md` archived**, not deleted. ADR-003 and ADR-004 reference them; the tool comparisons retain research value.
- **Rewrite AGENTS.md completely.** The old content describes pre-modernization module structure and would mislead any AI assistant into contributing to the wrong packages.
- **Update DOCKER.md minimally.** Docker operations are correct; only the UI tab name reference and the deprecated CLI invocation need updating.
- **Do not touch source code** beyond removing empty directories. Code comment cleanup (stale "Phase 4 will delete" comments in `src/utils/llm.py`) is a code maintenance task, not documentation governance.
