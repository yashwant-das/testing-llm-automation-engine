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


def fetch_accessibility_tree_dict(page) -> dict | None:
    """Fetch the accessibility tree via CDP (since Playwright Python lacks page.accessibility)."""
    try:
        cdp = page.context.new_cdp_session(page)
        raw_tree = cdp.send("Accessibility.getFullAXTree")
        nodes = raw_tree.get("nodes", [])
        if not nodes:
            return None

        node_map = {}
        for n in nodes:
            node_id = n.get("nodeId")
            role = n.get("role", {}).get("value", "")
            if not role:
                role = n.get("chromeRole", {}).get("value", "")
            if isinstance(role, int):
                role = str(role)
            name = n.get("name", {}).get("value", "")
            ignored = n.get("ignored", False)
            node_map[node_id] = {
                "role": role,
                "name": name,
                "children": [],
                "_child_ids": n.get("childIds", []),
                "_parent_id": n.get("parentId"),
                "ignored": ignored,
            }

        root = None
        for n in nodes:
            node_id = n.get("nodeId")
            mapped = node_map[node_id]
            parent_id = mapped.get("_parent_id")
            if parent_id and parent_id in node_map:
                node_map[parent_id]["children"].append(mapped)
            elif not parent_id:
                root = mapped

        def _filter_ignored(node):
            valid_children = []
            for child in node["children"]:
                filtered_child = _filter_ignored(child)
                if filtered_child["ignored"]:
                    valid_children.extend(filtered_child["children"])
                else:
                    valid_children.append(filtered_child)
            node["children"] = valid_children
            return node

        if root:
            root = _filter_ignored(root)

        return root
    except Exception as exc:
        logger.warning("CDP accessibility failed: %s", exc)
        return None


def collect_accessibility_tree(page) -> str:
    """Collect the Playwright accessibility tree from an open page.

    Args:
        page: An open Playwright ``Page`` object (already navigated).

    Returns:
        Formatted accessibility tree string, or an empty string on failure.
    """
    try:
        snapshot = fetch_accessibility_tree_dict(page)
        if not snapshot:
            logger.debug("Accessibility snapshot returned None")
            return ""
        return format_accessibility_snapshot(snapshot)
    except Exception as exc:
        logger.warning("Accessibility tree collection failed: %s", exc)
        return ""
