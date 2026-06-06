"""
Generation service — test generation and execution with streaming progress.

generate_test_streaming  yields (timeline_md, code) pairs for Gradio.
run_test_streaming       yields (timeline_md, logs) pairs for Gradio.

Both functions validate inputs, then delegate to the generator agent
(or directly to subprocess for test execution).  All LLM and subprocess
calls live here, not in app.py.
"""

import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEST_DIR = PROJECT_ROOT / "tests" / "generated"


def generate_test_streaming(url: str, story: str) -> Iterator[tuple[str, str]]:
    """Generate a Playwright test from a URL and user story, yielding progress.

    Args:
        url:   Target URL string (validated internally).
        story: User story / test scenario description (validated internally).

    Yields:
        (timeline_markdown, code_or_empty) — code is non-empty only on the
        final yield when generation succeeds.
    """
    from src.agents.generator import generate_test_script
    from src.utils.validation import (
        ValidationError,
        validate_and_sanitize_url,
        validate_description,
    )

    timeline = "### ⏱️ Generation Timeline\n\n"

    # --- Validate ---
    timeline += "🟢 **Input Validation**: Verifying target URL and user story...\n\n"
    yield timeline, ""

    try:
        validated_url = validate_and_sanitize_url(url)
        validated_story = validate_description(story)
    except ValidationError as exc:
        yield timeline + f"🔴 **Validation Error**: {exc}", f"Validation Error: {exc}"
        return
    except Exception as exc:
        yield timeline + f"🔴 **Error**: {exc}", f"Error: {exc}"
        return

    # --- Scan + Generate (both happen inside the agent) ---
    timeline += "🟢 **Scanning Web Page**: Accessing Chromium browser to capture DOM layout...\n\n"
    yield timeline, ""

    timeline += (
        "🧠 **LLM Inference**: Engineering script structure and selectors...\n\n"
    )
    yield timeline, ""

    code = generate_test_script(validated_url, validated_story)

    if not code or code.startswith(("Error", "LLM Error")):
        yield timeline + f"🔴 **Generation Error**: {code}", code
        return

    timeline += "✅ **Success**: Test script successfully generated!\n\n"
    yield timeline, code


def run_test_streaming(url: str, code: str, story: str) -> Iterator[tuple[str, str]]:
    """Write a generated test to disk and run it, yielding progress updates.

    Args:
        url:   Target URL (used to derive the filename domain prefix).
        code:  TypeScript test code to write and execute.
        story: Test scenario description (used to derive the filename slug).

    Yields:
        (timeline_markdown, logs_or_empty) — logs are non-empty on the final yield.
    """
    from src.utils.browser import extract_domain
    from src.utils.formatting import format_test_result
    from src.utils.validation import (
        ValidationError,
        validate_and_sanitize_url,
        validate_description,
    )

    timeline = "### ⏱️ Test Execution Timeline\n\n"
    timeline += "🟢 **Sanity Checks**: Verifying script inputs...\n\n"
    yield timeline, ""

    if not code or not code.strip():
        yield (
            timeline + "🔴 **Input Error**: No test code provided",
            "Error: No test code provided",
        )
        return

    try:
        validated_url = validate_and_sanitize_url(url)
        validated_story = validate_description(story) if story else "test"
    except ValidationError as exc:
        yield timeline + f"🔴 **Validation Error**: {exc}", f"Validation Error: {exc}"
        return
    except Exception as exc:
        yield timeline + f"🔴 **Error**: {exc}", f"Error: {exc}"
        return

    # --- Write spec file ---
    timeline += "🟢 **Writing Spec File**: Saving test script to workspace...\n\n"
    yield timeline, ""

    try:
        domain = extract_domain(validated_url)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_desc = re.sub(r"[^a-zA-Z0-9]", "_", validated_story).lower()
        clean_desc = re.sub(r"_+", "_", clean_desc)
        snake_desc = clean_desc[:40].strip("_")
        filename = f"{domain}_{snake_desc}_{timestamp}.spec.ts"

        TEST_DIR.mkdir(parents=True, exist_ok=True)
        filepath = TEST_DIR / filename
        filepath.write_text(code, encoding="utf-8")
    except Exception as exc:
        yield timeline + f"🔴 **File Error**: {exc}", f"Error writing file: {exc}"
        return

    # --- Run with Playwright ---
    timeline += f"🟢 **Playwright Test Runner**: Launching `npx playwright test {filename}`...\n\n"
    yield timeline, "Running tests in workspace..."

    try:
        result = subprocess.run(
            ["npx", "playwright", "test", str(filepath)],
            capture_output=True,
            text=True,
            timeout=45,
            cwd=str(PROJECT_ROOT),
        )

        if result.returncode == 0:
            timeline += "✅ **Test Passed**: Spec file ran successfully!\n\n"
            yield (
                timeline,
                format_test_result(str(filepath), result.stdout, success=True),
            )
        else:
            timeline += (
                "❌ **Test Failed**: Playwright returned non-zero exit code.\n\n"
            )
            raw_logs = result.stdout if result.stdout else result.stderr
            yield timeline, format_test_result(str(filepath), raw_logs, success=False)

    except subprocess.TimeoutExpired:
        timeline += (
            "🔴 **Timeout Error**: Playwright test timed out after 45 seconds.\n\n"
        )
        yield (
            timeline,
            f"Error: Test execution timed out after 45 seconds.\nStored in: {filepath}",
        )
    except FileNotFoundError:
        timeline += "🔴 **Environment Error**: Playwright executable not found.\n\n"
        yield (
            timeline,
            "Error: Playwright not found. Please run 'npx playwright install'",
        )
    except Exception as exc:
        timeline += f"🔴 **Execution Error**: {exc}\n\n"
        yield timeline, f"Execution Error: {exc}\nStored in: {filepath}"
