"""
LLM client utilities for OpenAI-compatible API interactions.

This module provides functions for initializing the LLM client, selecting models,
and extracting code blocks from LLM responses.
"""

import os
import re

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Configuration from environment variables
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "lm-studio")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
OLLAMA_API_KEY = "ollama"  # Ollama doesn't require an API key, but client expects one

# Provider selection (default: lm_studio)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "lm_studio").lower()

# Model Configuration
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen/qwen3-coder-30b")
LM_STUDIO_VISION_MODEL = os.getenv("LM_STUDIO_VISION_MODEL", "qwen/qwen3-vl-30b")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:26b")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "qwen3-vl:30b")

# Initialize client based on provider
try:
    if LLM_PROVIDER == "ollama":
        base_url = OLLAMA_URL
        api_key = OLLAMA_API_KEY
        print(f"Initializing OpenAI client with Ollama provider at {base_url}")
    else:  # default to lm_studio
        base_url = LM_STUDIO_URL
        api_key = LM_STUDIO_API_KEY
        print(f"Initializing OpenAI client with LM Studio provider at {base_url}")

    client = OpenAI(base_url=base_url, api_key=api_key)
except Exception as e:
    print(f"Warning: Failed to initialize OpenAI client: {e}")
    client = None


def get_client():
    """Get the configured OpenAI-compatible client instance.

    Returns:
        OpenAI: Configured client instance
    """
    return client


def get_model(vision=False):
    """Get the appropriate model name based on provider and use case.

    Args:
        vision: If True, returns vision model; otherwise returns default model

    Returns:
        str: Model name string
    """
    if LLM_PROVIDER == "ollama":
        return OLLAMA_VISION_MODEL if vision else OLLAMA_MODEL
    else:  # default to lm_studio
        return LM_STUDIO_VISION_MODEL if vision else LM_STUDIO_MODEL


def extract_code_block(llm_response):
    """Extract code block from LLM response text.

    Attempts to extract code from markdown code blocks, with fallback
    to cleaning up response text if no code block is found.

    Args:
        llm_response: Raw LLM response text

    Returns:
        str: Extracted code block, or cleaned response if no block found
    """
    if not llm_response:
        return ""
    # Standard markdown code block regex
    pattern = r"```(?:typescript|ts|javascript|js)?\n(.*?)```"
    match = re.search(pattern, llm_response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Fallback: Clean up prefix text or single line backticks
    llm_response = (
        llm_response.replace("```typescript", "")
        .replace("```ts", "")
        .replace("```", "")
        .strip()
    )

    lines = llm_response.split("\n")
    clean_lines = [
        line
        for line in lines
        if not line.lower().strip().startswith(("here", "sure", "certainly", "i have"))
    ]
    return "\n".join(clean_lines).strip()


def extract_json_block(llm_response):
    """Extract JSON block from LLM response text.

    Args:
        llm_response: Raw LLM response text

    Returns:
        str: Extracted JSON string
    """
    if not llm_response:
        return "{}"

    # Check for markdown code block
    pattern = r"```(?:json)?\n(.*?)```"
    match = re.search(pattern, llm_response, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
    else:
        # Fallback: look for first { and last }
        start = llm_response.find("{")
        end = llm_response.rfind("}")

        if start != -1 and end != -1:
            json_str = llm_response[start : end + 1]
        else:
            json_str = llm_response

    # Sanitization: Remove invalid control characters (0x00-0x1F) except \n, \r, \t
    # Also remove 0x7F (DEL)
    json_str = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", json_str)

    return json_str
