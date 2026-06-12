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
    from src.healing.artifact_store import emit_decision
    from src.observability import get_tracer
    from src.utils.validation import (
        ValidationError,
        validate_and_sanitize_url,
        validate_description,
    )

    tracer = get_tracer()
    trace_id = tracer.start_session("generation")
    timeline = "### Generation Timeline\n\n"

    # --- Validate ---
    timeline += "→ Input validation: checking URL and scenario...\n\n"
    yield timeline, ""

    try:
        validated_url = validate_and_sanitize_url(url)
        validated_story = validate_description(story)
    except ValidationError as exc:
        tracer.end_session(trace_id, success=False)
        yield timeline + f"❌ Validation error: {exc}", f"Validation Error: {exc}"
        return
    except Exception as exc:
        tracer.end_session(trace_id, success=False)
        yield timeline + f"❌ Error: {exc}", f"Error: {exc}"
        return

    # --- Scan + Generate (both happen inside the agent) ---
    timeline += "→ DOM collection: launching Chromium, collecting page structure...\n\n"
    yield timeline, ""

    timeline += "→ LLM call: generating test structure and selectors...\n\n"
    yield timeline, ""

    try:
        decision = generate_test_script(validated_url, validated_story)
    except Exception as exc:
        tracer.end_session(trace_id, success=False)
        yield timeline + f"❌ Generation error: {exc}", f"Error: {exc}"
        return

    decision.trace_id = trace_id
    emit_decision(decision, "generation_decision")
    tracer.end_session(trace_id, success=True)

    timeline += (
        f"✅ Generation complete — {decision.line_count} lines\n\n"
        f"── Model ──────────────────────────────────────\n\n"
        f"Provider : `{decision.provider}`  \n"
        f"Model    : `{decision.model_used}`  \n"
        f"Tokens   : {decision.input_tokens:,} in / {decision.output_tokens:,} out  \n"
        f"Latency  : {decision.latency_ms:,} ms  \n\n"
    )
    yield timeline, decision.code


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

    timeline = "### Test Execution Timeline\n\n"
    timeline += "→ Input validation: checking URL and code...\n\n"
    yield timeline, ""

    if not code or not code.strip():
        yield (
            timeline + "❌ Input error: no test code provided",
            "Error: No test code provided",
        )
        return

    try:
        validated_url = validate_and_sanitize_url(url)
        validated_story = validate_description(story) if story else "test"
    except ValidationError as exc:
        yield timeline + f"❌ Validation error: {exc}", f"Validation Error: {exc}"
        return
    except Exception as exc:
        yield timeline + f"❌ Error: {exc}", f"Error: {exc}"
        return

    # --- Write spec file ---
    timeline += "→ Writing spec file to tests/generated/...\n\n"
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
        yield timeline + f"❌ File error: {exc}", f"Error writing file: {exc}"
        return

    # --- Run with Playwright ---
    timeline += f"→ Playwright runner: `npx playwright test {filename}`\n\n"
    yield timeline, "Running tests..."

    try:
        result = subprocess.run(
            ["npx", "playwright", "test", str(filepath)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )

        if result.returncode == 0:
            timeline += "✅ Exit code 0 — test passed\n\n"
            yield (
                timeline,
                format_test_result(str(filepath), result.stdout, success=True),
            )
        else:
            timeline += f"❌ Exit code {result.returncode} — test failed\n\n"
            raw_logs = result.stdout if result.stdout else result.stderr
            yield timeline, format_test_result(str(filepath), raw_logs, success=False)

    except subprocess.TimeoutExpired:
        timeline += "❌ Timeout: Playwright did not complete within 60 seconds\n\n"
        yield (
            timeline,
            f"Error: Test execution timed out after 60 seconds.\nStored in: {filepath}",
        )
    except FileNotFoundError:
        timeline += "❌ Environment error: Playwright executable not found\n\n"
        yield (
            timeline,
            "Error: Playwright not found. Please run 'npx playwright install'",
        )
    except Exception as exc:
        timeline += f"❌ Execution error: {exc}\n\n"
        yield timeline, f"Execution Error: {exc}\nStored in: {filepath}"
