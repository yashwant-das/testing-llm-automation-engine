"""
LLM client utilities for OpenAI-compatible API interactions.

Public API:
  get_client()              — returns the configured OpenAI client
  get_model(vision=False)   — returns the model name for the current provider
  parse_llm_response()      — parse and validate an LLM response with Pydantic
  extract_code_block()      — legacy code extractor (used by app.py, deprecated)
  extract_json_block()      — legacy JSON extractor (kept for unit tests)
"""

import logging
import os
import re
from typing import Type, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------

LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "lm-studio")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
OLLAMA_API_KEY = "ollama"

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "lm_studio").lower()

LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen/qwen3-coder-30b")
LM_STUDIO_VISION_MODEL = os.getenv("LM_STUDIO_VISION_MODEL", "qwen/qwen3-vl-30b")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:26b")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "qwen3-vl:30b")

# ---------------------------------------------------------------------------
# Client initialisation (module-level singleton — Phase 2 will replace this
# with LLMClientFactory; kept here to avoid breaking existing callers)
# ---------------------------------------------------------------------------

try:
    if LLM_PROVIDER == "ollama":
        _base_url = OLLAMA_URL
        _api_key = OLLAMA_API_KEY
        logger.info("Initializing OpenAI client with Ollama provider at %s", _base_url)
    else:
        _base_url = LM_STUDIO_URL
        _api_key = LM_STUDIO_API_KEY
        logger.info(
            "Initializing OpenAI client with LM Studio provider at %s", _base_url
        )

    client = OpenAI(base_url=_base_url, api_key=_api_key)
except Exception as e:
    logger.warning("Failed to initialize OpenAI client: %s", e)
    client = None


def get_client() -> OpenAI:
    """Return the configured OpenAI-compatible client instance."""
    return client


def get_model(vision: bool = False) -> str:
    """Return the appropriate model name for the current provider.

    Args:
        vision: If True, return the vision-capable model.
    """
    if LLM_PROVIDER == "ollama":
        return OLLAMA_VISION_MODEL if vision else OLLAMA_MODEL
    return LM_STUDIO_VISION_MODEL if vision else LM_STUDIO_MODEL


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
    Kept for backward compatibility with app.py (removed in Phase 3).
    """
    return _extract_code_block(llm_response)


def extract_json_block(llm_response: str) -> str:
    """Extract a JSON string from an LLM response.

    Deprecated: use parse_llm_response() with a Pydantic model instead.
    Kept for backward compatibility with unit_test_json.py.
    """
    return _extract_json_block(llm_response)
