"""
Console error listener — captures browser console errors and warnings during
Playwright page navigation.

Attaches a listener to ``page.on("console", ...)`` that accumulates error and
warning messages in a mutable list.  The listener must be attached BEFORE
``page.goto()`` so events fired during navigation are captured.

Public API:
    attach_console_listener(page) -> list[str]
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Console message types to capture.  "error" and "warning" are most useful for
# diagnosing why a page behaves unexpectedly.
_CAPTURED_TYPES: frozenset[str] = frozenset({"error", "warning"})


def attach_console_listener(page) -> list[str]:
    """Attach a console error/warning listener to a Playwright page.

    Args:
        page: A Playwright ``Page`` object.  The listener is registered on
              ``page.on("console", ...)``.

    Returns:
        A mutable list that will be populated with captured messages as the
        page navigates.  Each entry is formatted as ``"[TYPE] message text"``.

    Note:
        Call this function BEFORE ``page.goto()`` so that messages emitted
        during navigation are captured.
    """
    messages: list[str] = []

    def _on_console(msg) -> None:
        if msg.type in _CAPTURED_TYPES:
            messages.append(f"[{msg.type.upper()}] {msg.text}")

    page.on("console", _on_console)
    return messages
