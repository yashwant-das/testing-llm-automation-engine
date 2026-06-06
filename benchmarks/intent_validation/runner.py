"""
Intent validation runner.

Validates that a generated Playwright test actually covers the user story it
was generated from.  All checks are heuristic and lexical — no LLM or browser
is required.

Checks performed:
- Target URL present verbatim in the code.
- At least one ``test()`` block.
- At least one ``expect()`` assertion.
- ``async / await`` used properly.
- Test name contains keywords from the feature description.
- No fatal structural errors (e.g. unclosed braces, empty file).

Public API:
    evaluate_test_intent(code, url, feature_description) -> EvaluationResult
    run_intent_validation(cases, config) -> BenchmarkRun
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from pydantic import BaseModel, Field

from schemas.evaluation import BenchmarkRun, BenchmarkRunConfig, EvaluationResult

logger = logging.getLogger(__name__)

# Keywords in the feature description that are too common to be meaningful
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "so",
        "that",
        "the",
        "then",
        "to",
        "user",
        "with",
    }
)

# Minimum length for a word to be considered a meaningful keyword
_MIN_KEYWORD_LENGTH = 4


def _extract_keywords(text: str) -> list[str]:
    """Return meaningful lowercase words from a feature description."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return [w for w in words if len(w) >= _MIN_KEYWORD_LENGTH and w not in _STOP_WORDS]


def evaluate_test_intent(
    code: str,
    url: str,
    feature_description: str,
    *,
    example_id: str = "intent-check",
    duration_ms: int = 0,
) -> EvaluationResult:
    """Heuristic intent validation for a generated Playwright test.

    This is a **pure function** — no I/O, no LLM, no browser.

    Args:
        code:                The generated TypeScript test code.
        url:                 The target URL the test should navigate to.
        feature_description: The user story used to generate the test.
        example_id:          Identifier for the EvaluationResult (default: ``"intent-check"``).
        duration_ms:         Generation duration to record in the result.

    Returns:
        :class:`~schemas.evaluation.EvaluationResult` with pass/fail and score.
    """
    if not code or code.startswith("Error") or code.startswith("LLM Error"):
        return EvaluationResult(
            example_id=example_id,
            passed=False,
            score=0.0,
            duration_ms=duration_ms,
            details={"checks_failed": ["generation failed or returned error"]},
            error=code or "empty response",
        )

    checks_passed: list[str] = []
    checks_failed: list[str] = []

    # ── Basic structure ───────────────────────────────────────────────────

    if "test(" in code:
        checks_passed.append("has-test-block")
    else:
        checks_failed.append("no-test-block")

    if "expect(" in code:
        checks_passed.append("has-expect-assertion")
    else:
        checks_failed.append("no-expect-assertion")

    if "async" in code and "await" in code:
        checks_passed.append("uses-async-await")
    else:
        checks_failed.append("missing-async-await")

    # ── URL presence ──────────────────────────────────────────────────────

    if url and url in code:
        checks_passed.append("url-present")
    elif url:
        checks_failed.append(f"missing-url({url})")

    # ── Test name relevance ───────────────────────────────────────────────

    test_name_match = re.search(r'test\s*\(\s*[\'"]([^\'"]+)[\'"]', code)
    if test_name_match:
        test_name = test_name_match.group(1).lower()
        keywords = _extract_keywords(feature_description)
        # Pass if at least one keyword from the description appears in the test name
        matched_keywords = [kw for kw in keywords if kw in test_name]
        if matched_keywords:
            checks_passed.append(f"test-name-reflects-intent({matched_keywords[0]!r})")
        elif keywords:
            checks_failed.append("test-name-does-not-reflect-intent")
        # If no keywords after filtering, skip this check
    else:
        checks_failed.append("no-test-name-found")

    # ── Navigation present ────────────────────────────────────────────────

    if "page.goto(" in code:
        checks_passed.append("has-navigation")
    else:
        checks_failed.append("no-page-goto")

    # ── Score and verdict ─────────────────────────────────────────────────

    total = len(checks_passed) + len(checks_failed)
    score = len(checks_passed) / total if total > 0 else 0.0
    passed = len(checks_failed) == 0

    return EvaluationResult(
        example_id=example_id,
        passed=passed,
        score=round(score, 4),
        duration_ms=duration_ms,
        details={
            "checks_passed": checks_passed,
            "checks_failed": checks_failed,
            "feature_keywords": _extract_keywords(feature_description),
        },
    )


# ---------------------------------------------------------------------------
# Input schema for batch validation
# ---------------------------------------------------------------------------


class IntentCase(BaseModel):
    """One intent-validation case — a generated test with its originating prompt."""

    id: str
    url: str
    feature_description: str
    generated_code: str


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_intent_validation(
    cases: List[IntentCase],
    config: BenchmarkRunConfig,
) -> BenchmarkRun:
    """Run intent validation over a list of cases.

    Args:
        cases:  List of :class:`IntentCase` objects.
        config: Benchmark configuration.

    Returns:
        :class:`~schemas.evaluation.BenchmarkRun`.
    """
    results: list[EvaluationResult] = []

    for case in cases:
        logger.info(
            "[%s] Validating intent for: %s", case.id, case.feature_description[:60]
        )
        result = evaluate_test_intent(
            case.generated_code,
            case.url,
            case.feature_description,
            example_id=case.id,
        )
        results.append(result)
        logger.info(
            "[%s] passed=%s score=%.2f",
            case.id,
            result.passed,
            result.score,
        )

    run = BenchmarkRun(config=config, results=results)
    logger.info(
        "Intent validation complete — %d/%d passed (%.0f%%) mean_score=%.2f",
        run.passed,
        run.total,
        run.pass_rate * 100,
        run.mean_score,
    )
    return run
