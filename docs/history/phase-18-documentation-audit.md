# Phase 18 — Documentation Reality Audit & Modernization

> Date: 2026-06-12
> Status: **Complete** — all fixes applied.
> Principle: the codebase is the source of truth, not prior documentation.

---

## Mission

Determine whether the documentation accurately reflects the repository. Correct
every wrong fact. Fill every gap. Remove stale content. The result is
documentation that a new contributor can trust.

---

## Documentation Inventory

Full audit of all 46 documents found in the repository.

### Root Level

| File | Status | Notes |
| --- | --- | --- |
| `README.md` | Needs Update | Tab count wrong (6→8), schema table incomplete, test count wrong (440→553) |
| `AGENTS.md` | Needs Update | Tab count, schema table, utils section, agent descriptions stale |

### `docs/`

| File | Status | Notes |
| --- | --- | --- |
| `docs/README.md` | Needs Update | Stale reading path, folder map errors |
| `docs/ai-systems-engineering.md` | Needs Update | `vision.py` reference wrong |
| `docs/backlog.md` | Needs Update | Two incorrect cleanup claims |
| `docs/decisions.md` | Needs Update | ADR-011 test count wrong |
| `docs/docker.md` | Current | No errors found |
| `docs/env-variables.md` | Needs Update | `LM_STUDIO_API_KEY` and `OLLAMA_API_KEY` missing |
| `docs/governance.md` | Current | No errors found |
| `docs/scorecard.md` | Needs Update | No post-Phase 17 notes |

### `docs/architecture/`

| File | Status | Notes |
| --- | --- | --- |
| `docs/architecture/generation.md` | Needs Update | Wrong return type, wrong participant (`vision.py`), stale sequence |
| `docs/architecture/healing.md` | Current | No errors found |
| `docs/architecture/llm-layer.md` | Needs Update | Test count wrong |
| `docs/architecture/overview.md` | Needs Update | "Phase 10" header, 6-tab layer map, schema table incomplete |

### `docs/development/`

| File | Status | Notes |
| --- | --- | --- |
| `docs/development/adding-benchmarks.md` | Current | No errors found |
| `docs/development/adding-healing-strategies.md` | Current | No errors found |
| `docs/development/adding-models.md` | Needs Update | `vision.py` reference wrong |
| `docs/development/debugging.md` | Needs Update | Wrong import path |
| `docs/development/setup.md` | Needs Update | Test count wrong |
| `docs/development/testing.md` | Needs Update | Test count, test file count, missing new test files |

### `docs/evaluation/`

| File | Status | Notes |
| --- | --- | --- |
| `docs/evaluation/benchmarks.md` | Needs Update | Tab name wrong ("Benchmark Explorer" → "Evaluation") |
| `docs/evaluation/reproducibility.md` | Needs Update | Tab name wrong |

### `docs/prompts/`

| File | Status | Notes |
| --- | --- | --- |
| `docs/prompts/generator.md` | Current | No errors found |
| `docs/prompts/healing.md` | Current | No errors found |
| `docs/prompts/manifest.md` | Current | No errors found |
| `docs/prompts/vision.md` | Current | No errors found |

### `docs/history/`

| File | Status | Notes |
| --- | --- | --- |
| `docs/history/README.md` | Needs Update | Missing entries for phases 15, 17, 18 |
| `docs/history/architecture-review.md` | Archive | Pre-modernization state — historical only |
| `docs/history/ast-evaluation.md` | Archive | ADR-003 recorded decision |
| `docs/history/documentation-audit.md` | Archive | Phase D1 audit — historical only |
| `docs/history/modernization-plan.md` | Archive | 11-phase plan — complete |
| `docs/history/observability-evaluation.md` | Archive | ADR-004 recorded decision |
| `docs/history/phase-12-documentation-modernization.md` | Archive | Phase complete |
| `docs/history/phase-13-quality-gates-modernization.md` | Archive | Phase complete |
| `docs/history/phase-14-repository-rationalization.md` | Archive | Phase complete |
| `docs/history/phase-16-ui-audit.md` | Archive | Findings addressed in Phase 17 |
| `docs/history/progress.md` | Archive | Phase 0–11 history |
| `docs/history/technical-debt.md` | Archive | All 15 items resolved |

### `progress/` (now archived)

| File | Status | Notes |
| --- | --- | --- |
| `progress/phase-15-experience-consistency.md` | → Archive | Moved to `docs/history/` |
| `progress/phase-17-workbench-redesign.md` | → Archive | Moved to `docs/history/` |

---

## Documentation Gaps

Eight facts that are true in code but not documented anywhere.

### Gap 1: Test Count and Test File Coverage

**What exists in code:** 553 Python unit tests across 16 files in `tests/unit_test_*.py`.

**What is documented:** "440 tests" appears in README, AGENTS.md, `docs/development/setup.md`,
`docs/development/testing.md`, `docs/architecture/llm-layer.md`, and `docs/decisions.md`.
The testing.md table lists 11 test files.

**Where to fix:** All six locations.

---

### Gap 2: Tab Count (6 vs. 8)

**What exists in code:** 8 Gradio tabs in `src/app.py` — Overview, Generation Pipeline,
Healing Pipeline, Vision Pipeline, Artifact Inspector, Evaluation (with sub-tabs), Trace
Inspector, Models.

**What is documented:** README says "six tabs" and lists only Generation, Healing, Vision,
Artifacts, Bench, Traces. AGENTS.md says "6-tab workbench". Architecture overview layer map
shows 6 tabs.

**Where to fix:** README, AGENTS.md, `docs/architecture/overview.md`.

---

### Gap 3: `GenerationDecision` and `VisionDecision` Schemas

**What exists in code:**

- `GenerationDecision` (`schemas/generation.py`): Full provenance artifact for generation
  runs. Includes URL, story, code, line count, context snapshot, and all
  `ProvenanceRecord` fields. Has `to_markdown()` method.
- `VisionDecision` (`schemas/generation.py`): Full provenance artifact for vision runs.
  Includes URL, instruction, code, line count, screenshot path.

**What is documented:** README schema table lists `GenerationResult` (the intermediate
validation model) but not `GenerationDecision` (the final artifact). `VisionDecision`
is not mentioned anywhere.

**Where to document:** README schema table; `docs/architecture/generation.md`;
`docs/architecture/overview.md`.

---

### Gap 4: Overview Tab

**What exists in code:** Tab 1 ("Overview") in the workbench provides:

- System overview summary (from `get_system_overview()` in `workbench_service.py`)
- Unified run history across all pipelines — one row per decision artifact, any type
  (from `load_run_history()`)

**What is documented:** Nowhere. README tab listing jumps straight to Generation Pipeline.

**Where to document:** README (Workbench section); `docs/architecture/overview.md`.

---

### Gap 5: Models Tab

**What exists in code:** Tab 8 ("Models") in the workbench shows active model
configuration from environment variables and capability metadata from `ModelRegistry`.

**What is documented:** Nowhere.

**Where to document:** README (Workbench section).

---

### Gap 6: `LLMConfig` Schema

**What exists in code:** `schemas/shared.py` contains `LLMConfig`, a Pydantic model
for LLM provider configuration (`provider`, `base_url`, `api_key`, `model`,
`vision_model`, `temperature`, `seed`).

**What is documented:** Not mentioned in any doc.

**Where to document:** `docs/architecture/llm-layer.md` (provider configuration section).

---

### Gap 7: `src/utils/browser.py` and `src/utils/formatting.py`

**What exists in code:**

- `src/utils/browser.py`: `extract_domain(url)` — extracts clean domain name for filenames.
- `src/utils/formatting.py`: `clean_ansi_codes()`, `format_test_result()` — ANSI
  stripping and test result formatting.

**What is documented:** Neither file is mentioned in README repo structure, AGENTS.md
module map, or any architecture document.

**Where to document:** README repo structure (utils section); AGENTS.md module map.

---

### Gap 8: `ProvenanceRecord` Base Class

**What exists in code:** `schemas/shared.py` contains `ProvenanceRecord`, a Pydantic
base model inherited by `HealingDecision`, `GenerationDecision`, and `VisionDecision`.
Fields: `model_used`, `provider`, `prompt_version`, `prompt_hash`, `input_tokens`,
`output_tokens`, `latency_ms`, `retry_count`, `trace_id`, `context_snapshot_id`,
`timestamp`.

**What is documented:** Not mentioned in any doc. README schema table shows only
`FailureType`, `RunResult` from `shared.py`.

**Where to document:** `docs/architecture/overview.md` data contracts table; README
schema table.

---

## Wrong Facts

Eleven specific factual errors with file and line citations (before fixes).

| # | File | Wrong Claim | Correct Fact |
| --- | --- | --- | --- |
| W-01 | `README.md:~90` | "six tabs" | 8 tabs |
| W-02 | `README.md` schema table | `GenerationResult` is the generation artifact | `GenerationDecision` is the artifact; `GenerationResult` is an internal validation model |
| W-03 | `README.md` repo structure | `src/agents/` described as "Agent shims (compatibility layer)" | `src/agents/` contains pipeline entry points |
| W-04 | `AGENTS.md` | `app.py` comment "6-tab workbench" | 8-tab workbench |
| W-05 | `docs/architecture/overview.md` header | "as of Phase 10" | as of Phase 17 |
| W-06 | `docs/architecture/overview.md` layer map | 6 tabs listed | 8 tabs (Overview, Generation, Healing, Vision, Artifacts, Evaluation, Traces, Models) |
| W-07 | `docs/architecture/generation.md` | `src/agents/vision.py` listed as a covered file | `src/agents/vision.py` does not exist; vision logic is in `src/services/vision_service.py` |
| W-08 | `docs/architecture/generation.md` sequence | `GEN-->>SVC: GenerationResult` | `GEN-->>SVC: GenerationDecision` |
| W-09 | `docs/development/debugging.md:38` | `from src.schemas.healing import Evidence` | `from schemas.healing import Evidence` |
| W-10 | `docs/backlog.md` | `extract_json_block()` listed as removal candidate | Private implementation inside `parse_llm_response()` — not a removal candidate |
| W-11 | `docs/evaluation/benchmarks.md` | "Benchmark Explorer" tab | Tab is named "Evaluation" since Phase 17 |

---

## Simplification Opportunities

Four areas where the documentation could be simplified without loss of accuracy.

1. **Merge `docs/architecture/generation.md` and `docs/architecture/healing.md`** — both
   describe pipeline architecture; a single "Pipelines" document would avoid duplication
   of the shared `ProvenanceRecord` pattern. (Not done — separate docs preferred for clarity.)

2. **Remove the stale "reading path" from `docs/README.md`** — one reading path pointed
   to Phase 16 as an open problem. Phase 17 resolved it. (Done.)

3. **Collapse `docs/env-variables.md` into the example `.env`** — the variable descriptions
   add little over what the code's defaults communicate. Not done — the descriptions clarify
   the `LLM_PROVIDER` switching logic which is non-obvious.

4. **Archive `progress/`** — the directory only contained phase tracking documents that
   belong in `docs/history/`. (Done — `progress/` removed after moving files.)

---

## Modernization Plan (Completed)

All items marked **Done** — Phase 18 is complete.

### High Priority (wrong facts or complete gaps)

| ID | Item | Status |
| --- | --- | --- |
| H-1 | Fix tab count (6→8) in README, AGENTS.md, architecture overview | Done |
| H-2 | Document Overview tab in README and architecture | Done |
| H-3 | Document Models tab in README | Done |
| H-4 | Fix `GenerationDecision` / `VisionDecision` in README schema table | Done |
| H-5 | Add `ProvenanceRecord` and `LLMConfig` to overview data contracts table | Done |
| H-6 | Fix `src/agents/vision.py` → `src/services/vision_service.py` everywhere | Done |
| H-7 | Fix test count 440 → 553 in all six locations | Done |
| H-8 | Add `browser.py` and `formatting.py` to README and AGENTS.md module maps | Done |

### Medium Priority (incomplete or stale content)

| ID | Item | Status |
| --- | --- | --- |
| M-1 | Update test file table in `docs/development/testing.md` (11→16 files) | Done |
| M-2 | Fix import path in `docs/development/debugging.md` | Done |
| M-3 | Fix `src/agents/` description in README (not "compatibility shims") | Done |
| M-4 | Fix `docs/backlog.md` cleanup claims | Done |
| M-5 | Add `LM_STUDIO_API_KEY` and `OLLAMA_API_KEY` to `docs/env-variables.md` | Done |
| M-6 | Fix evaluation tab name ("Benchmark Explorer" → "Evaluation") | Done |

### Low Priority (polish and completeness)

| ID | Item | Status |
| --- | --- | --- |
| L-1 | Update `docs/architecture/overview.md` header ("Phase 10" → "Phase 17") | Done |
| L-2 | Fix `docs/architecture/generation.md` sequence diagrams | Done |
| L-3 | Move progress files to `docs/history/` and remove `progress/` dir | Done |
| L-4 | Update `docs/history/README.md` with phases 15, 16, 17, 18 entries | Done |
| L-5 | Add post-Phase 17/18 notes to `docs/scorecard.md` | Done |

---

## Files Changed

| File | Change |
| --- | --- |
| `README.md` | Tab count, tab descriptions, schema table, repo structure, test count, footer link |
| `AGENTS.md` | Tab count, schema table, utils section, agent descriptions, test count |
| `docs/README.md` | Removed stale reading path; fixed folder map |
| `docs/ai-systems-engineering.md` | `vision.py` → `vision_service.py` |
| `docs/architecture/generation.md` | Fixed participant, return types, sequence |
| `docs/architecture/llm-layer.md` | Test count |
| `docs/architecture/overview.md` | Phase header, tab count, data contracts table |
| `docs/backlog.md` | Corrected two inaccurate cleanup claims |
| `docs/decisions.md` | Test count in ADR-011 |
| `docs/development/adding-models.md` | `vision.py` → `vision_service.py` |
| `docs/development/debugging.md` | Fixed import path |
| `docs/development/setup.md` | Test count |
| `docs/development/testing.md` | Test count, file count, added 4 new test file entries |
| `docs/env-variables.md` | Added `LM_STUDIO_API_KEY` and `OLLAMA_API_KEY` sections |
| `docs/evaluation/benchmarks.md` | Tab name |
| `docs/evaluation/reproducibility.md` | Tab name |
| `docs/history/README.md` | Added phases 15, 16, 17, 18 entries |
| `docs/scorecard.md` | Post-Phase 17/18 notes section |
| `docs/history/phase-15-experience-consistency.md` | Created (moved from `progress/`) |
| `docs/history/phase-17-workbench-redesign.md` | Created (moved from `progress/`) |
| `docs/history/phase-18-documentation-audit.md` | Created (this file) |
