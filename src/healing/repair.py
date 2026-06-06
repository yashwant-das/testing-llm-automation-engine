"""
Code repair — applies LLM-proposed fixes with indentation-tolerant string replacement.

Single responsibility: given the current file content and a HealingDecision,
return the updated source string.  Two strategies are tried in order:

  1. Exact string replacement (fast path).
  2. Normalized sliding-window match that strips leading whitespace from both
     the target block and the code window before comparing, then re-indents
     the replacement to match the indentation of the matched block.

No filesystem I/O — the caller is responsible for writing the returned string.
"""

import logging

from schemas.healing import HealingDecision

logger = logging.getLogger(__name__)


def apply_fix(file_path, current_code: str, decision: HealingDecision) -> str:
    """Apply the proposed code fix using exact match with normalized fallback.

    Args:
        file_path:    Path to the file being modified (used only for logging).
        current_code: Current file content as a string.
        decision:     HealingDecision containing the original and fixed code.

    Returns:
        Updated code string.  Returns ``current_code`` unchanged if neither
        strategy found a match.
    """
    target = decision.action_taken.original_code
    replacement = decision.action_taken.fixed_code

    if not target or not replacement:
        return current_code

    # Strategy 1: exact string replacement
    if target in current_code and (
        len(replacement.splitlines()) == 1
        or (
            len(target.splitlines()) > 1
            and (len(target) - len(target.lstrip()))
            == (len(replacement) - len(replacement.lstrip()))
        )
    ):
        return current_code.replace(target, replacement)

    # Strategy 2: normalized line match (tolerates indentation drift in LLM output)
    def normalize_lines(text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    target_lines = normalize_lines(target)
    code_lines = current_code.splitlines()

    for i in range(len(code_lines) - len(target_lines) + 1):
        window = [line.strip() for line in code_lines[i : i + len(target_lines)]]
        if window == target_lines:
            # Infer base indentation from the first matched line
            base_indent = code_lines[i][
                : len(code_lines[i]) - len(code_lines[i].lstrip())
            ]

            # Determine the base indentation of the replacement block
            replacement_lines = replacement.splitlines()
            non_empty = [line for line in replacement_lines if line.strip()]
            rep_base = (
                len(non_empty[0]) - len(non_empty[0].lstrip()) if non_empty else 0
            )

            # Re-indent replacement to match the matched block's indentation
            indented: list[str] = []
            for r_line in replacement_lines:
                if not r_line.strip():
                    indented.append("")
                else:
                    rel = max(0, (len(r_line) - len(r_line.lstrip())) - rep_base)
                    indented.append(base_indent + (" " * rel) + r_line.lstrip())

            new_lines = code_lines[:i] + indented + code_lines[i + len(target_lines) :]
            return "\n".join(new_lines)

    logger.warning(
        "Target code not found in file (exact or normalized).\nTarget:\n%s", target
    )
    return current_code
