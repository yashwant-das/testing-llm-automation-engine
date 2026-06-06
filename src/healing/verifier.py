"""
Verifier — post-repair test execution and pass/fail verdict.

Single responsibility: after a code fix has been written to disk, run the test
once more and update the HealingDecision's verification fields in-place.
Returns the RunResult so the caller can feed it forward into the next
gather_evidence() call without running the test a second time.
"""

import logging

from schemas.healing import HealingDecision
from schemas.shared import RunResult
from src.healing.runner import run_test

logger = logging.getLogger(__name__)


def verify_repair(test_file, decision: HealingDecision) -> RunResult:
    """Run the test after a repair and update the decision's verification fields.

    Mutates ``decision.verification_passed`` and ``decision.verification_log``
    in-place, then returns the RunResult for use in subsequent loop iterations.

    Args:
        test_file: Path-like pointing to the repaired .spec.ts file.
        decision:  HealingDecision to update with the verification outcome.

    Returns:
        RunResult from the post-repair test run.
    """
    result = run_test(test_file)
    decision.verification_passed = result.passed
    decision.verification_log = result.output
    logger.info(
        "Verification %s for %s",
        "PASSED" if result.passed else "FAILED",
        test_file,
    )
    return result
