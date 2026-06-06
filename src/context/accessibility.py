"""
Accessibility collector — Playwright accessibility tree as a formatted string.

Uses Playwright's ``page.accessibility.snapshot()`` API which returns the full
ARIA accessibility tree.  The tree is far more stable than raw HTML for
locator generation: it exposes roles, names, and semantic structure without
CSS noise.

Public API:
    collect_accessibility_tree(page) -> str
    format_accessibility_snapshot(snapshot_dict) -> str
"""

import logging

logger = logging.getLogger(__name__)


def format_accessibility_snapshot(node: dict, depth: int = 0) -> str:
    """Recursively format a Playwright accessibility snapshot dict as indented text.

    Args:
        node:  Raw accessibility tree node dict from ``page.accessibility.snapshot()``.
        depth: Current indentation depth (0 = root).

    Returns:
        Human-readable, indented representation of the node and its subtree.
    """
    indent = "  " * depth
    role = node.get("role", "unknown")
    name = node.get("name", "")
    line = f"{indent}[{role}] {name}" if name else f"{indent}[{role}]"
    parts = [line]
    for child in node.get("children", []):
        parts.append(format_accessibility_snapshot(child, depth + 1))
    return "\n".join(parts)


def collect_accessibility_tree(page) -> str:
    """Collect the Playwright accessibility tree from an open page.

    Args:
        page: An open Playwright ``Page`` object (already navigated).

    Returns:
        Formatted accessibility tree string, or an empty string on failure.
    """
    try:
        snapshot = page.accessibility.snapshot()
        if not snapshot:
            logger.debug("Accessibility snapshot returned None")
            return ""
        return format_accessibility_snapshot(snapshot)
    except Exception as exc:
        logger.warning("Accessibility tree collection failed: %s", exc)
        return ""
