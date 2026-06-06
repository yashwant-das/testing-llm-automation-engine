"""
Generation benchmark runner.

Evaluates the static code quality of Playwright tests produced by the generator.
Checks are purely lexical — no browser or LLM is invoked during evaluation.
The runner itself calls a ``generator_fn`` (injectable for testing) to produce
code for each scenario, then scores each output against the scenario's checks.

Public API:
    evaluate_generated_code(code, scenario) -> EvaluationResult
    load_dataset(path) -> GenerationDataset
    run_generation_benchmark(dataset_path, generator_fn, config) -> BenchmarkRun
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, List, Optional

from pydantic import BaseModel, Field

from schemas.evaluation import BenchmarkRun, BenchmarkRunConfig, EvaluationResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataset schemas (local to this runner)
# ---------------------------------------------------------------------------


class GenerationCheck(BaseModel):
    """Quality checks applied to a generated test file."""

    must_import: List[str] = Field(default_factory=list)
    """Strings that must appear anywhere in the generated code (e.g. ``"@playwright/test"``)."""

    must_use_assertions: List[str] = Field(default_factory=list)
    """Assertion helpers that must appear (e.g. ``"expect"``)."""

    must_not_use_deprecated: List[str] = Field(default_factory=list)
    """Deprecated APIs that must NOT appear (e.g. ``"waitForSelector"``)."""

    must_contain_url: bool = True
    """Whether the scenario URL must appear verbatim in the code."""

    preferred_locators: List[str] = Field(default_factory=list)
    """Modern Playwright locators whose presence boosts the score (not a hard gate)."""


class GenerationScenario(BaseModel):
    """One generation benchmark scenario."""

    id: str
    description: str
    url: str
    feature_description: str
    checks: GenerationCheck = Field(default_factory=GenerationCheck)


class GenerationDataset(BaseModel):
    """Full generation benchmark dataset loaded from JSON."""

    version: str
    description: str
    scenarios: List[GenerationScenario]


# ---------------------------------------------------------------------------
# Evaluator — pure function, no I/O
# ---------------------------------------------------------------------------

# Minimum fraction of checks that must pass for a non-zero score
_PASS_THRESHOLD = 1.0  # all mandatory checks must pass


def evaluate_generated_code(
    code: str,
    scenario: GenerationScenario,
    *,
    duration_ms: int = 0,
) -> EvaluationResult:
    """Evaluate generated TypeScript code against a scenario's checks.

    This is a **pure function** — it performs lexical checks only.  No browser,
    no LLM, no file I/O.

    Args:
        code:        The generated TypeScript test code (or an error string).
        scenario:    The scenario that was used to generate the code.
        duration_ms: How long generation took (set by the runner).

    Returns:
        :class:`~schemas.evaluation.EvaluationResult` with pass/fail and score.
    """
    if not code or code.startswith("Error") or code.startswith("LLM Error"):
        return EvaluationResult(
            example_id=scenario.id,
            passed=False,
            score=0.0,
            duration_ms=duration_ms,
            details={"checks_failed": ["generation failed or returned error"]},
            error=code or "empty response",
        )

    checks_passed: list[str] = []
    checks_failed: list[str] = []

    # ── Mandatory: must-import ────────────────────────────────────────────
    for imp in scenario.checks.must_import:
        if imp in code:
            checks_passed.append(f"import({imp})")
        else:
            checks_failed.append(f"missing-import({imp})")

    # ── Mandatory: must-use-assertions ───────────────────────────────────
    for assertion in scenario.checks.must_use_assertions:
        if assertion in code:
            checks_passed.append(f"assertion({assertion})")
        else:
            checks_failed.append(f"missing-assertion({assertion})")

    # ── Mandatory: must-not-use-deprecated ───────────────────────────────
    for deprecated in scenario.checks.must_not_use_deprecated:
        if deprecated in code:
            checks_failed.append(f"deprecated({deprecated})")
        else:
            checks_passed.append(f"no-deprecated({deprecated})")

    # ── Mandatory: URL present ────────────────────────────────────────────
    if scenario.checks.must_contain_url:
        if scenario.url in code:
            checks_passed.append("url-present")
        else:
            checks_failed.append(f"missing-url({scenario.url})")

    # ── Bonus: preferred locators (do not gate pass/fail) ─────────────────
    preferred_found = sum(
        1 for loc in scenario.checks.preferred_locators if loc in code
    )
    preferred_total = len(scenario.checks.preferred_locators)

    # Score = mandatory pass rate + small locator bonus
    mandatory_total = len(checks_passed) + len(checks_failed)
    base_score = len(checks_passed) / mandatory_total if mandatory_total > 0 else 0.0

    if preferred_total > 0:
        locator_ratio = preferred_found / preferred_total
        # Up to 10% bonus, only when base checks are already good
        bonus = 0.1 * locator_ratio * base_score
        score = min(1.0, base_score + bonus)
    else:
        score = base_score

    passed = len(checks_failed) == 0

    return EvaluationResult(
        example_id=scenario.id,
        passed=passed,
        score=round(score, 4),
        duration_ms=duration_ms,
        details={
            "checks_passed": checks_passed,
            "checks_failed": checks_failed,
            "preferred_locators_found": preferred_found,
            "preferred_locators_total": preferred_total,
        },
    )


# ---------------------------------------------------------------------------
# Dataset loader
# ---------------------------------------------------------------------------


def load_dataset(path: Path) -> GenerationDataset:
    """Load a generation dataset from a JSON file."""
    return GenerationDataset.model_validate_json(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_generation_benchmark(
    dataset_path: Path,
    generator_fn: Callable[[str, str], str],
    config: BenchmarkRunConfig,
    *,
    scenario_ids: Optional[List[str]] = None,
) -> BenchmarkRun:
    """Run the generation benchmark against a dataset.

    Calls ``generator_fn(url, feature_description)`` for each scenario in the
    dataset, then evaluates the returned code with :func:`evaluate_generated_code`.

    Args:
        dataset_path:  Path to ``web_scenarios.json``.
        generator_fn:  ``(url, feature_description) -> code_or_error_string``.
                       Inject a mock here for testing; use
                       ``src.agents.generator.generate_test_script`` in production.
        config:        Benchmark configuration (model, prompt hash, etc.).
        scenario_ids:  Optional subset of scenario IDs to evaluate.  All
                       scenarios are run if ``None``.

    Returns:
        :class:`~schemas.evaluation.BenchmarkRun` with per-scenario results.
    """
    dataset = load_dataset(dataset_path)
    scenarios = dataset.scenarios
    if scenario_ids is not None:
        scenarios = [s for s in scenarios if s.id in scenario_ids]

    results: list[EvaluationResult] = []

    for scenario in scenarios:
        logger.info("[%s] Generating: %s", scenario.id, scenario.description)
        t0 = time.monotonic()
        try:
            code = generator_fn(scenario.url, scenario.feature_description)
        except Exception as exc:
            code = f"Error: {exc}"
        duration_ms = int((time.monotonic() - t0) * 1000)

        result = evaluate_generated_code(code, scenario, duration_ms=duration_ms)
        results.append(result)
        logger.info(
            "[%s] score=%.2f passed=%s (%dms)",
            scenario.id,
            result.score,
            result.passed,
            result.duration_ms,
        )

    run = BenchmarkRun(config=config, results=results)
    logger.info(
        "Generation benchmark complete — %d/%d passed (%.0f%%) mean_score=%.2f",
        run.passed,
        run.total,
        run.pass_rate * 100,
        run.mean_score,
    )
    return run


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    from src.agents.generator import generate_test_script
    from src.llm import get_default_router
    from src.utils.prompt_loader import get_prompt_hash

    _router = get_default_router()
    _config = BenchmarkRunConfig(
        model=_router.primary_model,
        prompt_name="generator",
        prompt_version="1",
        prompt_hash=get_prompt_hash("generator"),
        dataset_version="1.0.0",
        benchmark_type="generation",
    )

    _dataset_path = Path(__file__).parent / "fixtures" / "web_scenarios.json"
    _run = run_generation_benchmark(_dataset_path, generate_test_script, _config)

    print(_run.to_json())
    sys.exit(0 if _run.pass_rate >= 0.8 else 1)
