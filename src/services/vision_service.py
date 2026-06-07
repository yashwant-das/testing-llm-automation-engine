"""
Vision service — screenshot capture and vision-LLM test generation with streaming.

analyze_visual_streaming     captures screenshot, calls vision LLM, yields progress.
run_vision_test_streaming    thin wrapper around run_test_streaming with relabelled timeline.
"""

import base64
import logging
import os
import re
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCREENSHOT_DIR = PROJECT_ROOT / "tests" / "screenshots"


def analyze_visual_streaming(
    url: str, instruction: str
) -> Iterator[tuple[str, Optional[str], str]]:
    """Capture a screenshot and analyze it with the vision LLM, yielding progress.

    The screenshot path is yielded as the second element of the tuple as soon as
    it is available (before the LLM call), so the Gradio image preview updates
    while the model is thinking.

    Args:
        url:         Target URL string (validated internally).
        instruction: Test scenario instruction (validated internally).

    Yields:
        (timeline_markdown, screenshot_path_or_None, code_or_empty)
    """
    from schemas.generation import GenerationResult
    from src.context.screenshot import capture_screenshot
    from src.llm import get_default_router
    from src.utils.llm import extract_code_block
    from src.utils.prompt_loader import load_prompt
    from src.utils.validation import (
        ValidationError,
        validate_and_sanitize_url,
        validate_description,
    )

    timeline = "### Vision Timeline\n\n"

    # --- Validate ---
    timeline += "→ Input validation: checking URL and instruction...\n\n"
    yield timeline, None, ""

    try:
        validated_url = validate_and_sanitize_url(url)
        validated_instruction = validate_description(instruction)
    except ValidationError as exc:
        yield (
            timeline + f"❌ Validation error: {exc}",
            None,
            f"Validation Error: {exc}",
        )
        return
    except Exception as exc:
        yield timeline + f"❌ Error: {exc}", None, f"Error: {exc}"
        return

    # --- Capture screenshot ---
    timeline += "→ Screenshot: launching Playwright, navigating to URL...\n\n"
    yield timeline, None, ""

    clean_inst = re.sub(r"[^a-zA-Z0-9\s]", "", validated_instruction).lower()
    snake_inst = "_".join(clean_inst.split())[:30]

    try:
        screenshot_path = capture_screenshot(
            validated_url,
            SCREENSHOT_DIR,
            tag=snake_inst,
            wait_ms=2000,
        )
    except Exception as exc:
        yield (
            timeline + f"❌ Screenshot error: {exc}",
            None,
            f"Error capturing screenshot: {exc}",
        )
        return

    if not os.path.exists(screenshot_path):
        yield (
            timeline + "❌ Screenshot not created",
            None,
            f"Error: Screenshot was not created at {screenshot_path}",
        )
        return

    # Yield screenshot preview before the (slow) LLM call
    timeline += "✅ Screenshot captured\n\n"
    yield timeline, screenshot_path, ""

    # --- Encode screenshot ---
    try:
        with open(screenshot_path, "rb") as f:
            base64_image = base64.b64encode(f.read()).decode("utf-8")
    except Exception as exc:
        yield (
            timeline + f"❌ Encoding error: {exc}",
            screenshot_path,
            f"Error: {exc}",
        )
        return

    # --- Vision LLM ---
    timeline += "→ LLM call: vision model analyzing screenshot...\n\n"
    yield timeline, screenshot_path, ""

    try:
        system_instruction = load_prompt("vision")
        router = get_default_router()
        llm_response = router.complete_vision(
            messages=[
                {"role": "system", "content": system_instruction},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"TARGET URL: {validated_url}\nUser Scenario: {validated_instruction}",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                    ],
                },
            ],
            temperature=0.1,
            max_tokens=2000,
        )

        if not llm_response.content:
            yield (
                timeline + "❌ LLM error: vision model returned empty response",
                screenshot_path,
                "Error: Vision LLM returned empty response",
            )
            return

        extracted = extract_code_block(llm_response.content)
        try:
            result = GenerationResult(code=extracted)
        except ValueError as exc:
            yield (
                timeline + f"❌ Code extraction error: {exc}",
                screenshot_path,
                f"Error: Could not extract valid code from vision LLM response: {exc}",
            )
            return

    except Exception as exc:
        yield (
            timeline + f"❌ LLM error: {exc}",
            screenshot_path,
            f"Vision LLM Error: {exc}",
        )
        return

    timeline += "✅ Generation complete\n\n"
    yield timeline, screenshot_path, result.code


def run_vision_test_streaming(
    url: str, code: str, instruction: str
) -> Iterator[tuple[str, str]]:
    """Run a vision-generated test, relabelling the timeline for the visual tab.

    Thin wrapper around generation_service.run_test_streaming.

    Yields:
        (timeline_markdown, logs_or_empty)
    """
    from src.services.generation_service import run_test_streaming

    for timeline_val, logs_val in run_test_streaming(url, code, instruction):
        yield (
            timeline_val.replace(
                "Test Execution Timeline", "Visual Test Execution Timeline"
            ),
            logs_val,
        )
