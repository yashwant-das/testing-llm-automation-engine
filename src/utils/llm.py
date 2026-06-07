"""
LLM response parsing utilities.

Public API:
  parse_llm_response(raw, model_class)  — validate an LLM response with Pydantic
  extract_json_block(response)           — extract a JSON string from an LLM response
  extract_code_block(response)           — extract a TypeScript/JS code block from an LLM response
"""

import logging
import re
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

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
        json_str = extract_json_block(raw_content)
        return model_class.model_validate_json(json_str)
    except (ValidationError, ValueError) as exc:
        raise ValueError(
            f"Could not parse LLM response as {model_class.__name__}.\n"
            f"Validation error: {exc}\n"
            f"Raw content (first 500 chars): {raw_content[:500]}"
        ) from exc


def extract_json_block(llm_response: str) -> str:
    """Extract a JSON string from an LLM response.

    Prefers a fenced ```json block; falls back to finding the outermost
    { … } pair.  Also strips invalid control characters that some models emit.

    Args:
        llm_response: Raw string returned by the LLM.

    Returns:
        Extracted JSON string, or the original string if no JSON block found.
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


def extract_code_block(llm_response: str) -> str:
    """Extract a TypeScript/JavaScript code block from an LLM response.

    Prefers a fenced ```typescript or ```ts block; falls back to stripping
    markdown artefacts from the raw text.

    Args:
        llm_response: Raw string returned by the LLM.

    Returns:
        Extracted code string, or empty string if response is empty.
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
