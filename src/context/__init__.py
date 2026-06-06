"""
Context collection package — unified page context for generation and healing.

The package opens a single browser session per ``collect_context()`` call and
collects HTML, accessibility tree, console errors, network failures, and
optionally a screenshot.

Public API:
    collect_context(url, **kwargs) -> ContextSnapshot
    capture_screenshot(url, output_dir, **kwargs) -> str
    capture_from_page(page, output_dir, **kwargs) -> str
"""

from src.context.collector import collect_context
from src.context.screenshot import capture_from_page, capture_screenshot

__all__ = [
    "collect_context",
    "capture_from_page",
    "capture_screenshot",
]
