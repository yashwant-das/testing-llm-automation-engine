"""
Network failure listener — captures failed HTTP requests during Playwright
page navigation.

Attaches a listener to ``page.on("requestfailed", ...)`` that accumulates
request failure records in a mutable list.  The listener must be attached
BEFORE ``page.goto()`` so failures during the initial page load are captured.

Public API:
    attach_network_listener(page) -> list[str]
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def attach_network_listener(page) -> list[str]:
    """Attach a network failure listener to a Playwright page.

    Args:
        page: A Playwright ``Page`` object.  The listener is registered on
              ``page.on("requestfailed", ...)``.

    Returns:
        A mutable list that will be populated with failure records as the page
        navigates.  Each entry is formatted as
        ``"METHOD URL [failure reason]"``.

    Note:
        Call this function BEFORE ``page.goto()`` so that failures during the
        initial navigation are captured.
    """
    failures: list[str] = []

    def _on_request_failed(request) -> None:
        method = request.method
        url = request.url
        reason = request.failure or "unknown"
        failures.append(f"{method} {url} [{reason}]")

    page.on("requestfailed", _on_request_failed)
    return failures
