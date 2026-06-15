"""
Context collector — single-session unified page context collection.

Opens ONE Playwright browser session, runs all requested collectors in sequence,
then closes.  This amortises browser startup cost and ensures all context types
(HTML, accessibility tree, console errors, network failures, screenshot) are
captured from the same page state.

Public API:
    collect_context(url, **kwargs) -> ContextSnapshot
"""

import logging
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright

from schemas.artifacts import ContextSnapshot
from src.context.accessibility import (
    fetch_accessibility_tree_dict,
    format_accessibility_snapshot,
)
from src.context.console import attach_console_listener
from src.context.dom import collect_dom
from src.context.locator_candidates import extract_locator_candidates
from src.context.network import attach_network_listener
from src.context.screenshot import capture_from_page

logger = logging.getLogger(__name__)


def collect_context(
    url: str,
    *,
    capture_html: bool = True,
    capture_a11y: bool = True,
    capture_screenshot: bool = False,
    capture_console: bool = True,
    capture_network: bool = True,
    max_html_chars: int = 30000,
    max_locator_candidates: int = 20,
    screenshot_dir: Optional[Path] = None,
    screenshot_tag: str = "",
    wait_ms: int = 2000,
) -> ContextSnapshot:
    """Navigate to url in a single browser session and collect all requested context.

    All collectors share the same page object so the browser is started only
    once.  On any navigation or collection error, a partial snapshot with the
    url populated is returned — the function never raises.

    Args:
        url:                    Target URL string.
        capture_html:           Collect cleaned HTML body via BeautifulSoup.
        capture_a11y:           Collect the ARIA accessibility tree and derive
                                locator candidates.
        capture_screenshot:     Capture a viewport screenshot.  Requires
                                ``screenshot_dir`` to be set.
        capture_console:        Capture console errors and warnings.
        capture_network:        Capture failed network requests.
        max_html_chars:         Maximum characters of cleaned HTML to retain.
        max_locator_candidates: Maximum ``getByRole`` candidates extracted from
                                the accessibility tree.
        screenshot_dir:         Directory to write the screenshot file.
                                Required when ``capture_screenshot=True``.
        screenshot_tag:         Filename tag inserted between domain and timestamp.
        wait_ms:                Milliseconds to wait after ``goto()`` for JS
                                to settle before collecting context.

    Returns:
        :class:`~schemas.artifacts.ContextSnapshot` populated with all
        successfully collected fields.  Unpopulated fields remain at their
        ``None`` / empty-list defaults.
    """
    snapshot = ContextSnapshot(url=url)

    try:
        logger.info("Collecting context from %s...", url)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = ctx.new_page()

            # Attach listeners BEFORE goto() so events during navigation are captured
            console_buf = attach_console_listener(page) if capture_console else []
            network_buf = attach_network_listener(page) if capture_network else []

            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
            except Exception as exc:
                logger.warning("Navigation failed for %s: %s", url, exc)
                browser.close()
                return snapshot

            if wait_ms > 0:
                time.sleep(wait_ms / 1000)

            if capture_html:
                snapshot.html = collect_dom(page, max_chars=max_html_chars) or None

            if capture_a11y:
                try:
                    raw_a11y = fetch_accessibility_tree_dict(page)
                    if raw_a11y:
                        snapshot.accessibility_tree = format_accessibility_snapshot(
                            raw_a11y
                        )
                        snapshot.locator_candidates = extract_locator_candidates(
                            raw_a11y, max_count=max_locator_candidates
                        )
                except Exception as exc:
                    logger.warning("Accessibility collection failed: %s", exc)

            if capture_screenshot and screenshot_dir is not None:
                try:
                    snapshot.screenshot_path = capture_from_page(
                        page,
                        output_dir=screenshot_dir,
                        tag=screenshot_tag,
                        url=url,
                    )
                except Exception as exc:
                    logger.warning("Screenshot capture failed: %s", exc)

            snapshot.console_errors = list(console_buf)
            snapshot.network_errors = list(network_buf)

            browser.close()

    except Exception as exc:
        logger.warning("Context collection failed for %s: %s", url, exc)

    return snapshot
