"""
Mutation engine — programmatic introduction of known failures into Playwright tests.

Each mutation corresponds to a real failure type the healer is trained to fix.
Mutators are pure functions: they take source code and return modified code (or
the original on no-match).  The top-level ``mutate()`` function applies a named
mutation to a file on disk.

Public API:
    apply_selector_drift(code, original_selector, broken_selector) -> str
    apply_timeout_reduction(code, target_ms) -> str
    apply_import_removal(code, symbol) -> str
    apply_assertion_swap(code, from_method, to_method) -> str
    mutate(source_file, mutation_type, **kwargs) -> MutationResult
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class MutationType(str, Enum):
    """Supported mutation types, each mapping to a FailureType the healer handles."""

    SELECTOR_DRIFT = "selector_drift"
    """Replace a stable selector (data-testid) with a fragile ID selector."""

    TIMEOUT_TOO_SHORT = "timeout_too_short"
    """Reduce timeout values so the test times out on slow pages."""

    MISSING_IMPORT = "missing_import"
    """Remove a named import from ``@playwright/test`` to cause ReferenceError."""

    ASSERTION_SWAP = "assertion_swap"
    """Swap an assertion method to one that is inappropriate for locators."""


class MutationResult(BaseModel):
    """Result of applying a mutation to a source file."""

    source_file: str
    mutation_type: MutationType
    description: str
    original_code: str
    mutated_code: str
    success: bool
    """True when the mutation produced a change (i.e. the pattern was found)."""
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Pure transformation functions
# ---------------------------------------------------------------------------


def apply_selector_drift(
    code: str,
    original_selector: str,
    broken_selector: str = "#old-button",
) -> str:
    """Replace ``original_selector`` with ``broken_selector`` everywhere in code.

    Args:
        code:              TypeScript source code.
        original_selector: The stable selector to replace (e.g. ``[data-testid="submit"]``).
        broken_selector:   The drifted selector to inject (e.g. ``#old-button``).

    Returns:
        Modified source code, or the original if the selector was not found.
    """
    return code.replace(original_selector, broken_selector)


def apply_timeout_reduction(code: str, target_ms: int = 1000) -> str:
    """Reduce all ``timeout: N`` values to ``target_ms``.

    Args:
        code:      TypeScript source code.
        target_ms: The new (too-small) timeout value in milliseconds.

    Returns:
        Modified source code.
    """
    return re.sub(r"timeout:\s*\d+", f"timeout: {target_ms}", code)


def apply_import_removal(code: str, symbol: str = "expect") -> str:
    """Remove a named symbol from the ``@playwright/test`` import.

    Handles the common patterns:
    - ``import { test, expect } from ...``  →  ``import { test } from ...``
    - ``import { expect, test } from ...``  →  ``import { test } from ...``
    - ``import { expect } from ...``        →  ``import {  } from ...``

    Args:
        code:   TypeScript source code.
        symbol: The named export to remove (default: ``"expect"``).

    Returns:
        Modified source code.
    """
    # Remove ", symbol" or "symbol," from import braces
    code = re.sub(rf",\s*{re.escape(symbol)}", "", code)
    code = re.sub(rf"{re.escape(symbol)},\s*", "", code)
    # Handle lone symbol in braces (e.g. "import { expect } from ...")
    code = re.sub(rf"\{{\s*{re.escape(symbol)}\s*\}}", "{}", code)
    return code


def apply_assertion_swap(
    code: str,
    from_method: str = "toBeVisible",
    to_method: str = "toBe",
    to_argument: str = "true",
) -> str:
    """Swap ``from_method()`` calls with ``to_method(to_argument)`` in expect chains.

    Args:
        code:         TypeScript source code.
        from_method:  The assertion method to replace (default: ``"toBeVisible"``).
        to_method:    The replacement method (default: ``"toBe"``).
        to_argument:  Argument for the replacement call (default: ``"true"``).

    Returns:
        Modified source code.
    """
    return re.sub(
        rf"\.{re.escape(from_method)}\(\)",
        f".{to_method}({to_argument})",
        code,
    )


# ---------------------------------------------------------------------------
# Top-level mutate() dispatcher
# ---------------------------------------------------------------------------


def mutate(
    source_file: Path,
    mutation_type: MutationType,
    **kwargs,
) -> MutationResult:
    """Apply a named mutation to a test file and return the result.

    Args:
        source_file:   Path to the ``.spec.ts`` file to mutate.
        mutation_type: Which mutation to apply.
        **kwargs:      Extra keyword arguments forwarded to the transformation
                       function (e.g. ``original_selector``, ``target_ms``).

    Returns:
        :class:`MutationResult` with ``success=True`` when the mutation changed
        the file.  ``success=False`` when the pattern was not found or an error
        occurred.
    """
    try:
        original_code = source_file.read_text(encoding="utf-8")
    except OSError as exc:
        return MutationResult(
            source_file=str(source_file),
            mutation_type=mutation_type,
            description=f"Could not read file: {exc}",
            original_code="",
            mutated_code="",
            success=False,
            error=str(exc),
        )

    try:
        if mutation_type == MutationType.SELECTOR_DRIFT:
            mutated = apply_selector_drift(original_code, **kwargs)
            description = f"Replaced selector with drifted version ({kwargs})"
        elif mutation_type == MutationType.TIMEOUT_TOO_SHORT:
            mutated = apply_timeout_reduction(original_code, **kwargs)
            description = f"Reduced timeout to {kwargs.get('target_ms', 1000)}ms"
        elif mutation_type == MutationType.MISSING_IMPORT:
            mutated = apply_import_removal(original_code, **kwargs)
            description = f"Removed '{kwargs.get('symbol', 'expect')}' from import"
        elif mutation_type == MutationType.ASSERTION_SWAP:
            mutated = apply_assertion_swap(original_code, **kwargs)
            description = f"Swapped assertion method ({kwargs})"
        else:
            raise ValueError(f"Unknown mutation type: {mutation_type}")

        return MutationResult(
            source_file=str(source_file),
            mutation_type=mutation_type,
            description=description,
            original_code=original_code,
            mutated_code=mutated,
            success=mutated != original_code,
        )

    except Exception as exc:
        return MutationResult(
            source_file=str(source_file),
            mutation_type=mutation_type,
            description=f"Mutation failed: {exc}",
            original_code=original_code,
            mutated_code=original_code,
            success=False,
            error=str(exc),
        )
