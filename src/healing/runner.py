"""
Test runner — subprocess management for Playwright test execution.

Single responsibility: run a .spec.ts file via npx playwright test and
return a structured RunResult.  No LLM calls, no file I/O beyond the
subprocess output.
"""

import logging
import subprocess
import time
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
    command = f"npx playwright test {test_file}"
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            ["npx", "playwright", "test", str(test_file)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        run_result = RunResult(
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        latency_ms = int((time.monotonic() - t0) * 1000)
        run_result = RunResult.from_timeout()
        exit_code = -1
    except FileNotFoundError:
        latency_ms = int((time.monotonic() - t0) * 1000)
        run_result = RunResult.from_error("Playwright not found")
        exit_code = -2

    # Observability — record subprocess span; silently no-op when no session is active.
    try:
        from src.observability import get_tracer

        get_tracer().record_subprocess(
            command=command,
            exit_code=exit_code,
            latency_ms=latency_ms,
        )
    except Exception:
        pass  # Observability must never break the main path.

    return run_result
