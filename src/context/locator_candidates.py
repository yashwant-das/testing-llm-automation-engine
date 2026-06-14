"""
Locator candidate extractor — derives stable Playwright locators from an
accessibility tree snapshot.

Walks the accessibility tree and emits ``getByRole()`` call strings for every
interactive or named element.  These candidates are passed to the generator
LLM so it can write locators that Playwright is most likely to resolve reliably.

Public API:
    extract_locator_candidates(snapshot_dict, max_count) -> list[str]
"""

from __future__ import annotations

# Roles that represent interactive or otherwise meaningful UI elements.
# Heading and img are included because they are often stable anchor points.
_INTERACTIVE_ROLES: frozenset[str] = frozenset(
    {
        "button",
        "checkbox",
        "combobox",
        "heading",
        "img",
        "link",
        "listbox",
        "menuitem",
        "radio",
        "searchbox",
        "slider",
        "spinbutton",
        "tab",
        "textbox",
    }
)


def extract_locator_candidates(snapshot: dict, max_count: int = 20) -> list[str]:
    """Extract stable ``getByRole`` locator strings from an accessibility snapshot.

    Walks the tree depth-first and stops once ``max_count`` candidates are
    collected.  Only roles in ``_INTERACTIVE_ROLES`` with a non-empty name
    are emitted.

    Args:
        snapshot:  Raw accessibility tree dict from ``page.accessibility.snapshot()``.
        max_count: Maximum number of candidates to return.

    Returns:
        List of Playwright locator expression strings, e.g.
        ``["getByRole('button', { name: 'Submit' })", ...]``.
    """
    candidates: list[str] = []
    _walk(snapshot, candidates, max_count)
    return candidates


def _walk(node: dict, candidates: list[str], max_count: int) -> None:
    if len(candidates) >= max_count:
        return
    role = node.get("role", "")
    name = node.get("name", "")
    if role in _INTERACTIVE_ROLES and name:
        escaped = name.replace("'", "\\'")
        candidates.append(f"getByRole('{role}', {{ name: '{escaped}' }})")
    for child in node.get("children", []):
        _walk(child, candidates, max_count)
