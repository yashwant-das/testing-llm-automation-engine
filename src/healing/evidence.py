"""
Evidence collection — gathers diagnostic artifacts after a Playwright test failure.

Single responsibility: given a failing RunResult and the test file path, produce
an Evidence object containing error logs, the most recent failure screenshot (if
any), and live page context (HTML, accessibility tree, console errors, network
failures, locator candidates) from the URL in the test file.
"""

import logging
import re
from pathlib import Path
from typing import Optional

from schemas.healing import Evidence
from schemas.shared import RunResult
from src.context import collect_context

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def extract_url_from_code(code: str) -> Optional[str]:
    """Extract the target URL from a ``page.goto()`` call in Playwright test code.

    Args:
        code: TypeScript source of the test file.

    Returns:
        The URL string if found, otherwise ``None``.
    """
    if not code:
        return None
    pattern = r"page\.goto\(['\"`](https?://[^\s'\"`]+)['\"`]\)"
    match = re.search(pattern, code)
    if match:
        return match.group(1)
    return None


def gather_evidence(test_file, result: RunResult) -> Evidence:
    """Collect evidence from a failed test run: logs, screenshot, and page context.

    Uses ``src.context.collect_context()`` to open a single browser session and
    collect HTML, accessibility tree, console errors, network failures, and
    locator candidates from the URL extracted from the test file.

    Args:
        test_file: Path-like pointing to the failing .spec.ts file.
        result:    RunResult from the most recent test execution.

    Returns:
        Evidence populated with all available context; degrades gracefully when
        the URL cannot be extracted or the page is unreachable.
    """
    logs = result.stderr if result.stderr else result.stdout

    # Most recent screenshot written to test-results/ by Playwright on failure
    screenshot_path: Optional[str] = None
    results_dir = PROJECT_ROOT / "test-results"
    if results_dir.exists():
        screenshots = list(results_dir.glob("**/*.png"))
        if screenshots:
            screenshot_path = str(max(screenshots, key=lambda p: p.stat().st_mtime))

    # Extract target URL from the test file source
    url: Optional[str] = None
    try:
        test_file_path = Path(test_file)
        if test_file_path.exists():
            code = test_file_path.read_text(encoding="utf-8")
            url = extract_url_from_code(code)
    except Exception as exc:
        logger.warning("Could not read test file for URL extraction: %s", exc)

    if url:
        try:
            logger.info("Collecting page context from %s...", url)
            snapshot = collect_context(
                url,
                capture_html=True,
                capture_a11y=True,
                capture_screenshot=False,  # Playwright's own screenshot is preferred
                capture_console=True,
                capture_network=True,
            )
            return Evidence.from_context_snapshot(
                error_log=logs,
                snapshot=snapshot,
                screenshot_path=screenshot_path,  # Playwright failure screenshot wins
            )
        except Exception as exc:
            logger.warning("Context collection failed: %s", exc)

    return Evidence(
        error_log=logs,
        screenshot_path=screenshot_path,
    )
