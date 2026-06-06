"""
Utility for loading LLM prompts from external markdown files.

Phase 9: Added get_prompt_version() to read version strings from
prompts/manifest.json.  The manifest stores human-set version labels;
hashes are always computed fresh from file content by get_prompt_hash().
"""

import hashlib
import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_MANIFEST_PATH = _PROJECT_ROOT / "prompts" / "manifest.json"
_manifest_cache: dict | None = None


def _load_manifest() -> dict:
    """Load (and cache) the prompts/manifest.json registry."""
    global _manifest_cache
    if _manifest_cache is None:
        if _MANIFEST_PATH.exists():
            _manifest_cache = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        else:
            _manifest_cache = {"prompts": {}}
    return _manifest_cache


def get_prompt_version(agent_name: str) -> str:
    """Return the human-set version string for a prompt from prompts/manifest.json.

    Falls back to ``"1"`` if the manifest does not exist or the agent is not
    listed.  Version strings are set manually when a prompt is intentionally
    changed; they are NOT computed from content (use :func:`get_prompt_hash`
    for content-based fingerprinting).

    Args:
        agent_name: Name of the agent (e.g., 'healer', 'generator', 'vision').

    Returns:
        Version string (e.g. ``"1"``, ``"2"``).
    """
    manifest = _load_manifest()
    prompts = manifest.get("prompts", {})
    return prompts.get(agent_name, {}).get("version", "1")


def load_prompt(agent_name: str) -> str:
    """Load a prompt from the prompts/ directory.

    Args:
        agent_name: Name of the agent (e.g., 'generator', 'healer', 'vision')

    Returns:
        str: Content of the prompt file
    """
    # Resolve the project root dynamically
    project_root = Path(__file__).resolve().parent.parent.parent
    prompt_path = project_root / "prompts" / f"{agent_name}.md"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def get_prompt_hash(agent_name: str) -> str:
    """Return the SHA-256 hex digest (first 16 chars) of a prompt file's content.

    Used by benchmark runners to record which prompt version was active during
    a run so results can be reproduced or compared across prompt iterations.

    Args:
        agent_name: Name of the agent (e.g., 'generator', 'healer', 'vision').

    Returns:
        16-character hex string derived from the prompt content.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    content = load_prompt(agent_name)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
