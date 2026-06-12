# Phase 15: Experience Consistency & Modernization Alignment

**Objective:** Eliminate inconsistencies between current architecture, standards, UX, and examples so the repository feels like a single coherent system.

---

## Findings

### F-01: Phase references in production source files

**Files:** `schemas/artifacts.py`, `schemas/evaluation.py`, `schemas/healing.py`, `schemas/shared.py`, `src/utils/prompt_loader.py`, `src/observability/__init__.py`, `src/healing/planner.py`, `src/services/workbench_service.py`, `src/healing/repair.py`
**Issue:** Inline "Phase N" comments reference the now-complete modernization program. These are implementation-history noise in production source files. Future contributors have no context for "Phase 6" or "Phase 9".
**Action:** Remove all phase references from source code. Keep in `docs/history/` only.
**Status:** DONE

### F-02: Runtime-generated spec files not gitignored

**File:** `.gitignore`
**Issue:** The gitignore comment says `# tests/generated/*.spec.ts (Commented out to allow the user to commit generated/demo tests)`. Two LLM-generated spec files from today's session are untracked. This creates noise and risks accidental commits of volatile runtime artifacts.
**Action:** Activate gitignore for `tests/generated/*.spec.ts` with explicit exceptions for `broken_example.spec.ts` and `framework_smoke.spec.ts`.
**Status:** DONE

### F-03: `framework_smoke.spec.ts` provides zero framework signal

**File:** `tests/generated/framework_smoke.spec.ts`
**Issue:** `expect(1 + 1).toBe(2)` does not exercise any framework capability. Phase 13 history acknowledged it provides "zero AI quality signal." For an engineer-facing project, `npm run test` should verify the test infrastructure actually works.
**Action:** Replace with a test that verifies Playwright framework imports, fixture loading, and that the project's broken test fixture exists and is syntactically meaningful.
**Status:** DONE

### F-04: `broken_example.spec.ts` has a typo in a comment

**File:** `tests/generated/broken_example.spec.ts`
**Issue:** `// BUG: Incorrect selector for the username field (shoud be '#username')` has a typo: "shoud" → "should".
**Action:** Fix typo. Comments are professional documentation; typos undermine credibility.
**Status:** DONE

### F-05: AGENTS.md labels `src/agents/` as "compatibility shims"

**File:** `AGENTS.md`
**Issue:** The module map describes `src/agents/generator.py` as "Compatibility shims (do not add new logic here)" and `src/agents/healer.py` as "Thin shim → src/healing/ + CLI entrypoint". This suggests the directory is vestigial/transitional — confusing to a new contributor.
**Action:** Describe `src/agents/` accurately: generator.py orchestrates the generation pipeline; healer.py is the CLI entrypoint for the healing pipeline.
**Status:** DONE

### F-06: `src/agents/healer.py` docstring uses backwards-compatibility framing

**File:** `src/agents/healer.py`
**Issue:** Docstring says "Re-exports all public symbols from src.healing for backwards-compatible imports." and "New code should import directly from src.healing or its sub-modules." This discourages use of the module and leaks implementation history.
**Action:** Reframe as what it is: the CLI entrypoint for the healing pipeline that also re-exports the pipeline API.
**Status:** DONE

### F-07: `src/healing/repair.py` labels string fallback as "legacy"

**File:** `src/healing/repair.py`
**Issue:** Comment `# ── string path (legacy, retained as fallback) ────────────────────────────────` labels a live code path as legacy. It isn't legacy — it's the intentional fallback when AST strategies produce no match.
**Action:** Rewrite comment to describe the actual architectural role.
**Status:** DONE

### F-08: `docs/development/setup.md` has placeholder clone URL

**File:** `docs/development/setup.md`
**Issue:** `git clone https://github.com/your-org/testing-llm-automation-engine` uses a placeholder org name.
**Action:** Replace with actual repo URL: `https://github.com/yashwant-das/testing-llm-automation-engine`
**Status:** DONE

### F-09: `backlog.md` Cleanup section references already-resolved items

**File:** `docs/backlog.md`
**Issue:** The Cleanup Work table lists `src/models/healing_model.py`, `src/tui/`, `src/memory/` as items with "Shim exists" or "Empty directory" status. All three were removed in Phase 14. The table is stale.
**Action:** Remove the completed items from the Cleanup section. Remaining items (deprecated shims in `src/utils/llm.py`) are still valid.
**Status:** DONE

### F-10: `scripts/setup_demo.py` uses prototype-era print statements and debug code

**File:** `scripts/setup_demo.py`
**Issue:** Uses emoji-heavy print statements and generates a test file with `console.log('Attempting to click non-existent button...')`. Engineering tooling should produce clean, professional output.
**Action:** Remove emoji from print output. Remove debug console.log from generated test content.
**Status:** DONE

### F-11: Generator prompt is minimal — 3 rules for a reference implementation

**File:** `prompts/generator.md`
**Issue:** The generator prompt has 3 rules and no guidance on modern Playwright locator strategy, test quality, or TypeScript conventions. The generated output is the user's first impression of the framework's capabilities.
**Action:** Expand with engineering-quality rules: selector hierarchy, assertion best practices, test structure.
**Status:** DONE

### F-12: Vision prompt is minimal — 4 rules

**File:** `prompts/vision.md`
**Issue:** Four rules is insufficient for a vision-based test generator that is a key differentiator of the workbench.
**Action:** Expand with consistent engineering-quality guidance matching the generator prompt standard.
**Status:** DONE

### F-13: `src/agents/healer.py` `__all__` includes `attempt_healing` which is not a top-level export

**File:** `src/agents/healer.py`
**Issue:** `attempt_healing` is listed in `__all__` but it's a higher-level orchestration function. Verify it exists in `src/healing/__init__.py`.
**Action:** Verify and document accurately.
**Status:** VERIFIED (exists in `src/healing/__init__.py`)

### F-14: `docs/env-variables.md` example `.env` shows both providers in a single file

**File:** `docs/env-variables.md`
**Issue:** The example `.env` at the bottom shows all variables for both providers simultaneously. This is valid but potentially confusing; a user might not understand that `LLM_PROVIDER` determines which is active.
**Action:** Add a clarifying note about provider selection. Already covered in setup.md — cross-reference.
**Status:** NOTED (not changed — setup.md is the canonical reference; env-variables.md is a reference doc)

---

## Modernization Actions

| # | Area | File(s) | Change |
| --- | --- | --- | --- |
| A-01 | Phase references | `schemas/*.py`, `src/**/*.py` | Removed all "Phase N" inline comments |
| A-02 | Gitignore | `.gitignore` | Activated ignore for runtime-generated specs |
| A-03 | Smoke test | `tests/generated/framework_smoke.spec.ts` | Replaced trivial 1+1 with meaningful infrastructure verification |
| A-04 | Demo fixture | `tests/generated/broken_example.spec.ts` | Fixed typo in comment |
| A-05 | AGENTS.md | `AGENTS.md` | Replaced "compatibility shims" with accurate module descriptions |
| A-06 | Healer agent | `src/agents/healer.py` | Rewrote docstring to reflect actual role |
| A-07 | Repair module | `src/healing/repair.py` | Reframed "legacy" comment accurately |
| A-08 | Setup doc | `docs/development/setup.md` | Fixed placeholder clone URL |
| A-09 | Backlog | `docs/backlog.md` | Removed completed cleanup items |
| A-10 | Demo script | `scripts/setup_demo.py` | Modernized output and test fixture content |
| A-11 | Generator prompt | `prompts/generator.md` | Expanded with engineering-quality rules |
| A-12 | Vision prompt | `prompts/vision.md` | Expanded with consistent rules |

---

## Verification

- [x] All unit tests pass: 440 passed in 2.78s
- [x] Playwright smoke test passes: 4 passed (348ms) — all infrastructure checks green
- [x] No "Phase N" references remain in `src/` or `schemas/`
- [x] `.gitignore` correctly ignores runtime-generated specs; demo fixtures (`broken_example.spec.ts`, `framework_smoke.spec.ts`) are explicitly exempted
