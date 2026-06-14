"""
DOM collector — cleaned HTML snapshot from an already-navigated Playwright page.

Strips script/style/SVG noise from the page HTML using BeautifulSoup so the
result is token-efficient when passed to an LLM.

Public API:
    collect_dom(page, max_chars) -> str
"""

import logging

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_STRIP_TAGS = ["script", "style", "svg", "path", "meta", "link", "noscript"]


def collect_dom(page, max_chars: int = 30000) -> str:
    """Collect and clean the HTML body from a Playwright page.

    Args:
        page:      An open Playwright ``Page`` object (already navigated).
        max_chars: Maximum characters of cleaned HTML to return.

    Returns:
        Cleaned HTML body as a string, or an empty string on failure.
    """
    try:
        content = page.content()
    except Exception as exc:
        logger.warning("Failed to get page content: %s", exc)
        return ""

    try:
        soup = BeautifulSoup(content, "html.parser")
        for tag in soup(_STRIP_TAGS):
            tag.decompose()
        if soup.body:
            return soup.body.prettify()[:max_chars]
        return ""
    except Exception as exc:
        logger.warning("Failed to parse HTML: %s", exc)
        return ""
