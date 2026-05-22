# Architecture & Design

> **Single Source of Truth** for the Testing LLM Automation Engine.
> Last Updated: May 2026

## 1. Problem Statement

Automated test healing is often a "black box." When a test breaks and is automatically fixed, engineering teams often ask:

1. _Why_ did it fail?
2. _Why_ did the agent choose this specific fix?
3. _Can I trust_ that this fix is correct and not just a lucky guess?

Many repair systems can patch tests without explaining their reasoning. They lack **explainability**, **intent-awareness**, and **provenance**.

**The Goal:** Build a system where every automated repair is accompanied by a structured `HealingDecision` that provides evidence, reasoning, and verification proof.

---

## 2. Agent Responsibilities

The system consists of three primary agents, each with strict boundaries:

### A. Generator Agent (`src/agents/generator.py`)

- **Input:** URL, User Story (Text).
- **Responsibility:** Generates the _initial_ Playwright TypeScript test.
- **Method:** DOM-based analysis (primary) or Vision-based (secondary).
- **Output:** A runnable `.spec.ts` file in `tests/generated/`.

### B. Vision Agent (`src/agents/vision.py`)

- **Input:** URL, Instruction.
- **Responsibility:** Provides visual understanding when DOM analysis is insufficient.
- **Method:** Captures screenshots, uses Vision LLM (guided by `prompts/vision.md`) to interpret UI layout.
- **Output:** Generates test code based on visual cues.

### C. Healer Agent (`src/agents/healer.py`)

- **Input:** Path to a failing `.spec.ts` file.
- **Responsibility:** Diagnoses failure, hypothesizes root cause, gathers evidence, patches the code, and verifies the fix.
- **Key Feature:** **Hybrid Intelligence**. Uses Regex Heuristics for 100% confidence patterns and LLM (guided by `prompts/healer.md`) for complex reasoning.
- **Output:**
  1. Patched test file.
  2. `HealingDecision` JSON (Evidence + Reasoning).
  3. `ExecutionTimeline` JSON (Audit trail).

---

## 3. Healing Decision Pipeline

The Healer Agent operates in a strict, explainable pipeline:

1. **Failure Detection (Monitor)**
   - Runs the test via Playwright.
   - Parses logs for errors (`TimeoutError`, `TargetClosedError`, assertion output, `404/500`, `ReferenceError`, `TypeError`).
   - **Evidence Gathering**: Automatically scans `test-results/` for the latest screenshot path and records it in the artifact when Playwright captured one.

2. **Deterministic Classification (Heuristics)**
   - **Regex Layer**: Matches logs against known failure patterns (including network and JS errors).
   - **Confidence Score**: Assigns 1.0 (Heuristic match) or <1.0 (LLM hypothesis).

3. **LLM Reasoning (Investigate & Reason)**
   - Consults the LLM with the failing code, error logs, and heuristic diagnosis so it can confirm or refine the failure type.
   - Generates a **Hypothesis** and **Action Plan**.

4. **Remediation (Act)**
   - Propose a specific code change.
   - **Robustness Layer**: Uses fuzzy indentation matching to apply fixes even if LLM output is slightly malformed.

5. **Verification (Confirm)**
   - Re-runs the patched test.
   - Records the result (Pass/Fail).

6. **UI Surfacing (Visualize)**
   - Emits JSON artifacts to `tests/artifacts/`.
   - **Gradio Dashboard** reads these to render an **Execution Timeline** and **Decision Inspector** after each healing run.

---

## 4. Determinism & Quality Control

1. **Bounded Execution:** Max healing attempts per test run to prevent loops.
2. **Structured Data:** All decisions follow strict JSON schemas (see `src/models/healing_model.py`).
3. **Professional Pipeline**:
   - **JS/TS**: Linted with ESLint 9 (Playwright plugin) and formatted with Prettier.
   - **Python**: Linted and formatted with Ruff.
   - **Enforcement**: Husky pre-commit hooks run lint-staged checks before commits in local development.

## 5. Confidence Score Calculation

The `confidence_score` is calculated through a tiered approach in `src/agents/healer.py`:

| Component           | Logic                                                                   | Typical Score   |
| :------------------ | :---------------------------------------------------------------------- | :-------------- |
| **Heuristic Layer** | Scans logs for hardcoded Regex patterns (e.g., `TimeoutError`, `404`).  | **1.0**         |
| **LLM Reasoning**   | Analyzes complex failures by correlating logs with source code context. | **0.75 - 0.95** |
| **Default/Unknown** | Fallback when no evidence strongly correlates to a known issue.         | **0.0 - 0.5**   |

Scores are preserved in the `HealingDecision` artifact for auditability.

---

## 6. Quality Control & DX (Developer Experience)

To ensure this project remains maintainable and professional, we've implemented a robust "Pre-flight" pipeline:

- **Strict Linting**:
  - **Python**: `ruff` for ultra-fast linting, import sorting, and formatting.
  - **TypeScript**: `eslint` (v9 Flat Config) with the Playwright plugin for best practices.
  - **Documentation**: `markdownlint-cli2` ensures all docs follow GFM standards.
- **Git Hooks (Husky)**: Every `git commit` triggers a `pre-commit` hook that runs `lint-staged`. This prevents malformed or unformatted code from entering the repository.
- **Explainability First**: Healing runs produce structured JSON artifacts with evidence, reasoning summaries, code changes, and verification results.
