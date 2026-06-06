"""
Utility for loading LLM prompts from external markdown files.
"""

import hashlib
from pathlib import Path


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
