"""
Vision-based test generation agent using screenshot analysis.

Captures a UI screenshot and uses a vision-capable LLM to generate a
Playwright test script based on visual analysis.  The LLM response is
validated through GenerationResult before returning.
"""

import base64
import logging
import os
import re
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

from schemas.generation import GenerationResult
from src.llm import get_default_router
from src.utils.browser import extract_domain
from src.utils.llm import _extract_code_block
from src.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

SCREENSHOT_DIR = "tests/screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def encode_image(image_path: str) -> str:
    """Encode an image file to base64 for the vision LLM API.

    Args:
        image_path: Path to the PNG/JPEG screenshot file.

    Returns:
        Base64-encoded string of the image bytes.

    Raises:
        FileNotFoundError: If the image file does not exist.
        IOError: If the file cannot be read.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Screenshot not found: {image_path}")
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except IOError as exc:
        raise IOError(f"Error reading screenshot: {exc}") from exc


def analyze_visual_ui(url: str, instruction: str) -> str:
    """Analyze a UI with a vision LLM and return a generated test script.

    Captures a screenshot of the target URL, calls the vision model, then
    validates the extracted code through GenerationResult.

    Args:
        url: Validated URL string.
        instruction: Validated instruction describing the action to perform.

    Returns:
        Generated TypeScript test code, or an error message string.
    """
    try:
        domain = extract_domain(url)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        clean_inst = re.sub(r"[^a-zA-Z0-9\s]", "", instruction).lower()
        snake_inst = "_".join(clean_inst.split())[:30]
        screenshot_name = f"{domain}_{snake_inst}_{timestamp}.png"
        screenshot_path = os.path.join(SCREENSHOT_DIR, screenshot_name)

        os.makedirs(SCREENSHOT_DIR, exist_ok=True)

        # Capture screenshot
        logger.info("Capturing screenshot for %s...", url)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1280, "height": 720})
                page = context.new_page()
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2)
                page.screenshot(path=screenshot_path)
                browser.close()
        except Exception as exc:
            return f"Error capturing screenshot: {exc}"

        if not os.path.exists(screenshot_path):
            return f"Error: Screenshot was not created at {screenshot_path}"

        # Encode screenshot for vision API
        try:
            base64_image = encode_image(screenshot_path)
        except (FileNotFoundError, IOError) as exc:
            return f"Error encoding image: {exc}"

        system_instruction = load_prompt("vision")

        logger.info("Analyzing UI with vision model...")
        router = get_default_router()
        try:
            llm_response = router.complete_vision(
                messages=[
                    {"role": "system", "content": system_instruction},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"TARGET URL: {url}\nUser Scenario: {instruction}",
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
                return "Error: Vision LLM returned empty response"

            raw_content = llm_response.content
            extracted = _extract_code_block(raw_content)

            # Validate via GenerationResult
            try:
                result = GenerationResult(code=extracted)
            except ValueError as exc:
                return f"Error: Could not extract valid code from vision LLM response: {exc}"

            return result.code

        except Exception as exc:
            return f"Vision LLM Error: {exc}"

    except Exception as exc:
        return f"Error analyzing visual UI: {exc}"
