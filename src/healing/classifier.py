"""
Failure classifier — deterministic heuristic classification of Playwright test failures.

Single responsibility: inspect log text and return a (FailureType, confidence, reason)
triple without making LLM calls or touching the filesystem.  The output feeds
planner.analyze_and_plan() as a pre-diagnosis hint.
"""

from schemas.shared import FailureType


def classify_failure_heuristic(logs: str) -> tuple[FailureType, float, str]:
    """Deterministically classify a failure from log patterns.

    The rules are ordered from highest to lowest specificity.  The first
    matching rule wins.

    Args:
        logs: Combined stderr / stdout from a failed Playwright test run.

    Returns:
        ``(FailureType, confidence, reasoning)`` where confidence is in [0.0, 1.0].
    """
    if not logs:
        return (FailureType.UNKNOWN, 0.0, "No logs available")

    if (
        "TimeoutError" in logs
        or "waiting for selector" in logs
        or "waiting for locator" in logs
        or "Test execution timed out" in logs
    ):
        return (
            FailureType.TIMEOUT,
            1.0,
            "Detected 'TimeoutError', 'waiting for selector', or 'waiting for locator' in logs",
        )

    if "TargetClosedError" in logs or "browser has been closed" in logs:
        return (
            FailureType.ENVIRONMENT_ISSUE,
            1.0,
            "Detected 'TargetClosedError' or browser crash",
        )

    if "expect(" in logs and "received" in logs:
        return (
            FailureType.ASSERTION_FAILED,
            1.0,
            "Detected 'expect(...)' assertion failure",
        )

    if "Error: strict mode violation" in logs:
        return (
            FailureType.LOCATOR_DRIFT,
            0.9,
            "Strict mode violation: multiple elements match selector",
        )

    if "locator resolved to 0 elements" in logs:
        if "Did you mean" in logs:
            return (
                FailureType.LOCATOR_DRIFT,
                0.8,
                "Locator failed but Playwright suggested content alternative",
            )
        return (FailureType.LOCATOR_NOT_FOUND, 0.7, "Locator resolved to 0 elements")

    if "net::ERR_ABORTED" in logs or "404" in logs or "500" in logs:
        return (
            FailureType.POTENTIAL_APP_DEFECT,
            0.8,
            "Detected network error or HTTP failure status code",
        )

    if "ReferenceError" in logs or "TypeError" in logs:
        return (
            FailureType.JAVASCRIPT_ERROR,
            0.7,
            "Detected JavaScript runtime error in logs",
        )

    return (FailureType.UNKNOWN, 0.0, "No specific pattern matched")
