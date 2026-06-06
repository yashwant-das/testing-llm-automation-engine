"""
Healing benchmark runner.

Evaluates failure classification accuracy and (optionally) repair quality.

Two evaluation modes:
  1. **Classification-only** (default): runs ``classify_failure_heuristic()``
     against the synthetic error log for each case and checks the result against
     ``checks.expected_failure_type``.  No LLM or browser required.
  2. **Full repair** (opt-in): additionally calls ``healer_fn(code, error_log)``
     and evaluates the repaired code against the ``checks`` criteria.

Public API:
    evaluate_classification(case, classified_type) -> bool
    evaluate_repair(case, original, repaired, classified_type, **kwargs) -> EvaluationResult
    load_dataset(path) -> HealingDataset
    run_healing_benchmark(dataset_path, project_root, config, healer_fn=None) -> BenchmarkRun
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, List, Optional

from pydantic import BaseModel, Field

from schemas.evaluation import BenchmarkRun, BenchmarkRunConfig, EvaluationResult
from src.healing.classifier import classify_failure_heuristic

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataset schemas
# ---------------------------------------------------------------------------


class HealingCheck(BaseModel):
    """Quality checks for a healed test file."""

    expected_failure_type: Optional[str] = None
    """The FailureType string the heuristic should classify this as."""

    must_fix_pattern: Optional[str] = None
    """String that must NOT appear in the repaired code (i.e. the bug was fixed)."""

    fixed_code_must_contain: List[str] = Field(default_factory=list)
    """Strings that MUST appear in the repaired code."""

    code_must_change: bool = True
    """Whether the repair must produce a code change at all."""


class HealingCase(BaseModel):
    """One healing benchmark case."""

    id: str
    description: str
    broken_test_file: str
    """Path relative to the project root (e.g. ``"tests/fixtures/broken_selector.spec.ts"``)."""

    injected_failure_type: str
    """The failure type that was deliberately introduced."""

    error_log: str
    """Synthetic error log that would appear when the broken test is run."""

    checks: HealingCheck = Field(default_factory=HealingCheck)


class HealingDataset(BaseModel):
    """Full healing benchmark dataset loaded from JSON."""

    version: str
    description: str
    cases: List[HealingCase]


# ---------------------------------------------------------------------------
# Evaluators — pure functions, no I/O (except file reads for repair mode)
# ---------------------------------------------------------------------------


def evaluate_classification(case: HealingCase, classified_type: str) -> bool:
    """Return True when classified_type matches the expected failure type.

    If ``case.checks.expected_failure_type`` is ``None``, always returns True
    (classification is not under test for this case).
    """
    if not case.checks.expected_failure_type:
        return True
    return classified_type == case.checks.expected_failure_type


def evaluate_repair(
    case: HealingCase,
    original_code: str,
    repaired_code: str,
    classified_type: str,
    *,
    duration_ms: int = 0,
) -> EvaluationResult:
    """Evaluate the quality of a repair against the case's checks.

    This is a **pure function** — lexical checks only, no I/O.

    Args:
        case:          The healing case being evaluated.
        original_code: The broken test file content before repair.
        repaired_code: The code produced by the healer.
        classified_type: The FailureType string returned by the classifier.
        duration_ms:   How long the classification + repair took.

    Returns:
        :class:`~schemas.evaluation.EvaluationResult`.
    """
    checks_passed: list[str] = []
    checks_failed: list[str] = []

    # ── Classification accuracy ───────────────────────────────────────────
    if case.checks.expected_failure_type:
        if classified_type == case.checks.expected_failure_type:
            checks_passed.append(f"classification({classified_type})")
        else:
            checks_failed.append(
                f"classification: expected={case.checks.expected_failure_type} got={classified_type}"
            )

    # ── Code changed ──────────────────────────────────────────────────────
    if case.checks.code_must_change:
        if repaired_code != original_code:
            checks_passed.append("code-modified")
        else:
            checks_failed.append("code-not-modified")

    # ── Must-fix pattern (must NOT appear in repaired code) ───────────────
    if case.checks.must_fix_pattern:
        if case.checks.must_fix_pattern not in repaired_code:
            checks_passed.append(f"fixed({case.checks.must_fix_pattern!r})")
        else:
            checks_failed.append(f"not-fixed({case.checks.must_fix_pattern!r})")

    # ── Fixed code must contain ───────────────────────────────────────────
    for pattern in case.checks.fixed_code_must_contain:
        if pattern in repaired_code:
            checks_passed.append(f"contains({pattern!r})")
        else:
            checks_failed.append(f"missing({pattern!r})")

    total = len(checks_passed) + len(checks_failed)
    score = len(checks_passed) / total if total > 0 else 0.0
    passed = len(checks_failed) == 0

    return EvaluationResult(
        example_id=case.id,
        passed=passed,
        score=round(score, 4),
        duration_ms=duration_ms,
        details={
            "checks_passed": checks_passed,
            "checks_failed": checks_failed,
            "classified_type": classified_type,
        },
    )


# ---------------------------------------------------------------------------
# Dataset loader
# ---------------------------------------------------------------------------


def load_dataset(path: Path) -> HealingDataset:
    """Load a healing dataset from a JSON file."""
    return HealingDataset.model_validate_json(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_healing_benchmark(
    dataset_path: Path,
    project_root: Path,
    config: BenchmarkRunConfig,
    *,
    healer_fn: Optional[Callable[[str, str], str]] = None,
    case_ids: Optional[List[str]] = None,
) -> BenchmarkRun:
    """Run the healing benchmark.

    For each case:
    1. Runs ``classify_failure_heuristic(case.error_log)``.
    2. If ``healer_fn`` is provided, calls it to get repaired code.
    3. Evaluates classification accuracy and (if repair is available) repair quality.

    Args:
        dataset_path:  Path to ``repair_scenarios.json``.
        project_root:  Project root for resolving ``case.broken_test_file`` paths.
        config:        Benchmark configuration.
        healer_fn:     Optional ``(broken_code, error_log) -> repaired_code``.
                       When ``None``, only classification accuracy is tested.
        case_ids:      Optional subset of case IDs to run.  All cases run if ``None``.

    Returns:
        :class:`~schemas.evaluation.BenchmarkRun`.
    """
    dataset = load_dataset(dataset_path)
    cases = dataset.cases
    if case_ids is not None:
        cases = [c for c in cases if c.id in case_ids]

    results: list[EvaluationResult] = []

    for case in cases:
        test_file = project_root / case.broken_test_file
        if not test_file.exists():
            logger.warning("[%s] Test file not found: %s", case.id, test_file)
            results.append(
                EvaluationResult(
                    example_id=case.id,
                    passed=False,
                    score=0.0,
                    error=f"Test file not found: {test_file}",
                    details={},
                )
            )
            continue

        original_code = test_file.read_text(encoding="utf-8")
        logger.info("[%s] Evaluating: %s", case.id, case.description)

        t0 = time.monotonic()

        # Step 1: heuristic classification
        failure_type, confidence, reason = classify_failure_heuristic(case.error_log)
        classified_type = str(failure_type.value)

        # Step 2 (optional): repair
        if healer_fn is not None:
            try:
                repaired_code = healer_fn(original_code, case.error_log)
            except Exception as exc:
                duration_ms = int((time.monotonic() - t0) * 1000)
                logger.error("[%s] healer_fn raised: %s", case.id, exc)
                results.append(
                    EvaluationResult(
                        example_id=case.id,
                        passed=False,
                        score=0.0,
                        duration_ms=duration_ms,
                        error=str(exc),
                        details={"classified_type": classified_type},
                    )
                )
                continue
        else:
            # Classification-only mode: use original code as "repair" so code
            # checks are skipped (code_must_change will fail, but we override)
            repaired_code = original_code

        duration_ms = int((time.monotonic() - t0) * 1000)

        # For classification-only mode, skip code mutation checks
        if healer_fn is None:
            # Build a classification-only result
            cls_ok = evaluate_classification(case, classified_type)
            results.append(
                EvaluationResult(
                    example_id=case.id,
                    passed=cls_ok,
                    score=1.0 if cls_ok else 0.0,
                    duration_ms=duration_ms,
                    details={
                        "classified_type": classified_type,
                        "expected_type": case.checks.expected_failure_type,
                        "confidence": confidence,
                        "reason": reason,
                        "mode": "classification-only",
                    },
                )
            )
        else:
            result = evaluate_repair(
                case,
                original_code,
                repaired_code,
                classified_type,
                duration_ms=duration_ms,
            )
            results.append(result)

        logger.info(
            "[%s] classified=%s expected=%s passed=%s score=%.2f (%dms)",
            case.id,
            classified_type,
            case.checks.expected_failure_type,
            results[-1].passed,
            results[-1].score,
            results[-1].duration_ms,
        )

    run = BenchmarkRun(config=config, results=results)
    logger.info(
        "Healing benchmark complete — %d/%d passed (%.0f%%) mean_score=%.2f",
        run.passed,
        run.total,
        run.pass_rate * 100,
        run.mean_score,
    )
    return run
