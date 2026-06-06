"""
LLM client utilities for OpenAI-compatible API interactions.

Public API:
  get_client()              — deprecated shim; returns a client via LLMClientFactory
  get_model(vision=False)   — deprecated shim; returns model via LLMRouter
  parse_llm_response()      — parse and validate an LLM response with Pydantic
  extract_code_block()      — legacy code extractor (deprecated, no callers; Phase 4 will delete)
  extract_json_block()      — legacy JSON extractor (kept for unit_test_json.py; Phase 4 will delete)

Note: get_client() and get_model() are deprecated and will be removed in Phase 3
when app.py is replaced with the service layer. All new code should import
from src.llm directly:

    from src.llm import get_default_router
    response = get_default_router().complete_primary(messages=[...])
"""

import logging
import re
from typing import Type, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Deprecated shims — delegate to src.llm (Phase 3 will remove these)
# ---------------------------------------------------------------------------


def get_client() -> OpenAI:
    """Return a configured OpenAI-compatible client.

    Deprecated: use src.llm.get_default_router() instead.
    Kept for backward compatibility with app.py (removed in Phase 3).
    """
    from src.llm.client import LLMClientFactory

    return LLMClientFactory.from_env()


def get_model(vision: bool = False) -> str:
    """Return the appropriate model name for the current provider.

    Deprecated: use src.llm.get_default_router().primary_model or .vision_model instead.
    Kept for backward compatibility with app.py (removed in Phase 3).

    Args:
        vision: If True, return the vision-capable model.
    """
    from src.llm import get_default_router

    router = get_default_router()
    return router.vision_model if vision else router.primary_model


# ---------------------------------------------------------------------------
# Structured-output parsing (Phase 1 addition)
# ---------------------------------------------------------------------------

T = TypeVar("T", bound=BaseModel)


def parse_llm_response(raw_content: str, model_class: Type[T]) -> T:
    """Parse and validate an LLM response string into a Pydantic model.

    Attempts two strategies in order:
      1. Direct JSON parse (model returned clean JSON).
      2. Extract a JSON block from markdown fences, then parse.

    Raises:
        ValueError: if neither strategy produces a valid model instance.

    Args:
        raw_content: Raw string returned by the LLM.
        model_class: Pydantic BaseModel subclass to validate against.

    Returns:
        A validated instance of model_class.
    """
    if not raw_content:
        raise ValueError(
            f"LLM returned an empty response; cannot parse as {model_class.__name__}."
        )

    # Strategy 1: direct parse
    try:
        return model_class.model_validate_json(raw_content)
    except (ValidationError, ValueError):
        pass

    # Strategy 2: extract JSON from markdown and retry
    try:
        json_str = _extract_json_block(raw_content)
        return model_class.model_validate_json(json_str)
    except (ValidationError, ValueError) as exc:
        raise ValueError(
            f"Could not parse LLM response as {model_class.__name__}.\n"
            f"Validation error: {exc}\n"
            f"Raw content (first 500 chars): {raw_content[:500]}"
        ) from exc


# ---------------------------------------------------------------------------
# Internal extraction helpers
# ---------------------------------------------------------------------------


def _extract_json_block(llm_response: str) -> str:
    """Extract a JSON string from an LLM response.

    Internal helper used by parse_llm_response().  Prefers a fenced ```json
    block; falls back to finding the outermost { … } pair.  Also strips
    invalid control characters that some models emit.
    """
    if not llm_response:
        return "{}"

    # Fenced code block
    pattern = r"```(?:json)?\n(.*?)```"
    match = re.search(pattern, llm_response, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
    else:
        # Brace-slice fallback
        start = llm_response.find("{")
        end = llm_response.rfind("}")
        if start != -1 and end != -1:
            json_str = llm_response[start : end + 1]
        else:
            json_str = llm_response

    # Strip invalid control characters (0x00–0x08, 0x0b, 0x0c, 0x0e–0x1f, 0x7f)
    json_str = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", json_str)
    return json_str


def _extract_code_block(llm_response: str) -> str:
    """Extract a TypeScript/JavaScript code block from an LLM response.

    Internal helper.  Prefers a fenced ```typescript or ```ts block;
    falls back to stripping markdown artefacts from the raw text.
    """
    if not llm_response:
        return ""

    pattern = r"```(?:typescript|ts|javascript|js)?\n(.*?)```"
    match = re.search(pattern, llm_response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Fallback: strip common preamble lines and backtick artefacts
    cleaned = (
        llm_response.replace("```typescript", "")
        .replace("```ts", "")
        .replace("```", "")
        .strip()
    )
    lines = cleaned.split("\n")
    lines = [
        line
        for line in lines
        if not line.lower().strip().startswith(("here", "sure", "certainly", "i have"))
    ]
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Legacy public aliases (maintained for app.py and unit_test_json.py)
# Phase 2 / Phase 3 will remove all external callers.
# ---------------------------------------------------------------------------


def extract_code_block(llm_response: str) -> str:
    """Extract a TypeScript code block from an LLM response.

    Deprecated: use parse_llm_response() with GenerationResult instead.
    No remaining callers — will be deleted in Phase 4.
    """
    return _extract_code_block(llm_response)


def extract_json_block(llm_response: str) -> str:
    """Extract a JSON string from an LLM response.

    Deprecated: use parse_llm_response() with a Pydantic model instead.
    Kept for backward compatibility with unit_test_json.py.
    """
    return _extract_json_block(llm_response)
