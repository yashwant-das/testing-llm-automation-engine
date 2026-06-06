"""
Test runner — subprocess management for Playwright test execution.

Single responsibility: run a .spec.ts file via npx playwright test and
return a structured RunResult.  No LLM calls, no file I/O beyond the
subprocess output.
"""

import logging
import subprocess
from pathlib import Path

from schemas.shared import RunResult

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def run_test(test_file) -> RunResult:
    """Run a Playwright test file and return a structured RunResult.

    Args:
        test_file: Path-like object or string pointing to a .spec.ts file.

    Returns:
        RunResult with returncode, stdout, stderr and a convenience ``passed``
        property (returncode == 0).
    """
    logger.info("Running %s...", test_file)
    try:
        result = subprocess.run(
            ["npx", "playwright", "test", str(test_file)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        return RunResult(
            returncode=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )
    except subprocess.TimeoutExpired:
        return RunResult.from_timeout()
    except FileNotFoundError:
        return RunResult.from_error("Playwright not found")
