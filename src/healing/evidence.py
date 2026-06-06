"""
Evidence collection — gathers diagnostic artifacts after a Playwright test failure.

Single responsibility: given a failing RunResult and the test file path, produce
an Evidence object containing error logs, the most recent failure screenshot (if
any), and a live DOM snippet from the page under test.
"""

import logging
import re
from pathlib import Path
from typing import Optional

from schemas.healing import Evidence
from schemas.shared import RunResult
from src.utils.browser import fetch_page_context

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
    """Collect evidence from a failed test run: logs, screenshot, DOM snippet.

    Args:
        test_file: Path-like pointing to the failing .spec.ts file.
        result:    RunResult from the most recent test execution.

    Returns:
        Evidence with error_log, optional screenshot_path, optional dom_snippet.
    """
    logs = result.stderr if result.stderr else result.stdout

    # Most recent screenshot written to test-results/ by Playwright
    screenshot_path = None
    results_dir = PROJECT_ROOT / "test-results"
    if results_dir.exists():
        screenshots = list(results_dir.glob("**/*.png"))
        if screenshots:
            screenshot_path = str(max(screenshots, key=lambda p: p.stat().st_mtime))

    # Live DOM from the URL in the test file
    dom_snippet = None
    try:
        test_file_path = Path(test_file)
        if test_file_path.exists():
            code = test_file_path.read_text(encoding="utf-8")
            url = extract_url_from_code(code)
            if url:
                logger.info("Fetching DOM context from %s...", url)
                dom_snippet = fetch_page_context(url)
                if dom_snippet and dom_snippet.startswith("Error"):
                    logger.warning("Failed to fetch DOM context: %s", dom_snippet)
                    dom_snippet = None
    except Exception as exc:
        logger.warning("Error gathering DOM context evidence: %s", exc)

    return Evidence(
        error_log=logs,
        screenshot_path=screenshot_path,
        dom_snippet=dom_snippet,
    )
