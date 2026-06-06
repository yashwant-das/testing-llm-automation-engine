"""
Screenshot capture — thin wrappers over Playwright screenshot functionality.

Two entry points:
  capture_screenshot(url, output_dir, ...)
      Opens its own browser session, navigates to url, captures, closes.
      Use when no existing browser session is open.

  capture_from_page(page, output_dir, ...)
      Uses an already-open Playwright page.  Use inside collector.py or
      any service that already has a browser open to avoid double startup.

Public API:
    capture_screenshot(url, output_dir, *, tag, wait_ms, ...) -> str
    capture_from_page(page, output_dir, *, tag, url) -> str
"""

import logging
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def _build_filename(url: str, tag: str) -> str:
    """Build a deterministic screenshot filename from url and tag."""
    from urllib.parse import urlparse

    try:
        netloc = urlparse(url).netloc
        domain = netloc.replace("www.", "").split(".")[0] or "page"
    except Exception:
        domain = "page"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{domain}_{tag}_{timestamp}.png" if tag else f"{domain}_{timestamp}.png"


def capture_screenshot(
    url: str,
    output_dir: Path,
    *,
    tag: str = "",
    wait_ms: int = 2000,
    viewport_width: int = 1280,
    viewport_height: int = 720,
) -> str:
    """Launch a headless browser, navigate to url, and capture a screenshot.

    Args:
        url:            Target URL.
        output_dir:     Directory to save the screenshot.  Created if absent.
        tag:            Short label inserted into the filename (e.g. instruction slug).
        wait_ms:        Milliseconds to wait after navigation before capturing.
        viewport_width: Browser viewport width in pixels.
        viewport_height: Browser viewport height in pixels.

    Returns:
        Absolute path to the saved PNG file.

    Raises:
        Exception: Propagates any Playwright or filesystem error.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / _build_filename(url, tag)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": viewport_width, "height": viewport_height}
        )
        page = context.new_page()
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        if wait_ms > 0:
            time.sleep(wait_ms / 1000)
        page.screenshot(path=str(path))
        browser.close()

    logger.info("Screenshot saved: %s", path)
    return str(path)


def capture_from_page(
    page,
    output_dir: Path,
    *,
    tag: str = "",
    url: str = "",
) -> str:
    """Capture a screenshot from an already-open Playwright page.

    Args:
        page:       An open Playwright ``Page`` object (already navigated).
        output_dir: Directory to save the screenshot.  Created if absent.
        tag:        Short label inserted into the filename.
        url:        Source URL used to derive the domain prefix in the filename.
                    Falls back to ``"page"`` if empty or unparseable.

    Returns:
        Absolute path to the saved PNG file.

    Raises:
        Exception: Propagates any Playwright or filesystem error.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / _build_filename(url, tag)
    page.screenshot(path=str(path))
    logger.info("Screenshot saved: %s", path)
    return str(path)
