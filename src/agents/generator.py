"""
Test generation agent for creating Playwright test scripts.

Generates TypeScript Playwright tests from a URL and feature description
by fetching page context and calling an LLM.  The LLM response is validated
through GenerationResult before any code is written to disk.
"""

import logging
import os
import re
import subprocess
import sys
from datetime import datetime

from schemas.generation import GenerationResult
from src.llm import get_default_router
from src.utils.browser import extract_domain
from src.utils.formatting import format_test_result
from src.utils.llm import _extract_code_block
from src.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

TEST_DIR = "tests/generated"
os.makedirs(TEST_DIR, exist_ok=True)


def generate_test_script(url: str, feature_description: str) -> str:
    """Generate a Playwright test script from a URL and feature description.

    Args:
        url: Validated URL string.
        feature_description: Validated feature description string.

    Returns:
        Generated TypeScript test code, or an error message string.
    """
    try:
        logger.info("Generating test for URL: %s", url)

        from src.context import collect_context

        snapshot = collect_context(url, capture_html=True, capture_a11y=True)

        if not snapshot.html and not snapshot.accessibility_tree:
            return f"Error: Failed to fetch page context from {url}"

        # Build a richer PAGE CONTEXT block from the snapshot
        context_parts: list[str] = []
        if snapshot.html:
            context_parts.append(snapshot.html)
        if snapshot.accessibility_tree:
            context_parts.append(
                f"ACCESSIBILITY TREE:\n{snapshot.accessibility_tree[:5000]}"
            )
        if snapshot.locator_candidates:
            cands = "\n".join(f"  - {c}" for c in snapshot.locator_candidates)
            context_parts.append(f"LOCATOR CANDIDATES (prefer these):\n{cands}")
        if snapshot.console_errors:
            errs = "\n".join(snapshot.console_errors[:5])
            context_parts.append(f"CONSOLE ERRORS:\n{errs}")

        html_context = "\n\n".join(context_parts)

        system_instruction = load_prompt("generator")
        user_prompt = f"""
TARGET URL: {url}
USER STORY: {feature_description}
PAGE CONTEXT: {html_context}
"""

        router = get_default_router()
        try:
            llm_response = router.complete_primary(
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
            )

            if not llm_response.content:
                return "Error: LLM returned empty response"

            raw_content = llm_response.content
            extracted = _extract_code_block(raw_content)

            # Validate via GenerationResult — raises ValueError if code is empty
            try:
                result = GenerationResult(code=extracted)
            except ValueError as exc:
                return f"Error: Could not extract valid code from LLM response: {exc}"

            return result.code

        except Exception as exc:
            return f"LLM Error: {exc}"

    except Exception as exc:
        return f"Error generating test script: {exc}"


def run_generated_test(url: str, code_snippet: str, description: str = "test") -> str:
    """Run a generated test script using Playwright.

    Args:
        url: Validated URL string.
        code_snippet: TypeScript test code to run.
        description: Test description used in the filename.

    Returns:
        Test execution result message (pass/fail with logs).
    """
    if not code_snippet or not code_snippet.strip():
        return "Error: No test code provided"

    try:
        domain = extract_domain(url)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        clean_desc = re.sub(r"[^a-zA-Z0-9]", "_", description).lower()
        clean_desc = re.sub(r"_+", "_", clean_desc)
        snake_desc = clean_desc[:40].strip("_")

        filename = f"{domain}_{snake_desc}_{timestamp}.spec.ts"
        filepath = os.path.join(TEST_DIR, filename)

        os.makedirs(TEST_DIR, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code_snippet)

        logger.info("Running %s...", filename)

        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )

        try:
            result = subprocess.run(
                ["npx", "playwright", "test", filepath],
                capture_output=True,
                text=True,
                timeout=45,
                cwd=project_root,
            )
            if result.returncode == 0:
                return format_test_result(filepath, result.stdout, success=True)
            logs = result.stdout if result.stdout else result.stderr
            return format_test_result(filepath, logs, success=False)

        except subprocess.TimeoutExpired:
            return f"Error: Test execution timed out after 45 seconds.\nStored in: {filepath}"
        except FileNotFoundError:
            return "Error: Playwright not found. Please run 'npx playwright install'"
        except Exception as exc:
            return f"Execution Error: {exc}\nStored in: {filepath}"

    except Exception as exc:
        return f"Error running test: {exc}"
