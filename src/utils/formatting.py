"""
Formatting utilities for the application.
"""

import re
from typing import Optional


def clean_ansi_codes(text: str) -> str:
    """Remove ANSI escape sequences from text.

    Args:
        text: Input string containing potential ANSI codes

    Returns:
        str: Cleaned string
    """
    if not text:
        return ""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def format_test_result(
    filepath: str,
    output: str,
    success: bool,
    metadata: Optional[dict] = None,
) -> str:
    """Format the test execution result for display.

    Args:
        filepath: Path to the test file
        output:   Raw output from the test execution
        success:  Whether the test passed or failed
        metadata: Optional dict with keys: provider, model, input_tokens,
                  output_tokens, latency_ms

    Returns:
        str: Formatted user-friendly message
    """
    cleaned_output = clean_ansi_codes(output)
    cleaned_output = cleaned_output.replace("To open last HTML report run:", "")
    cleaned_output = cleaned_output.replace("npx playwright show-report", "")
    cleaned_output = cleaned_output.strip()

    status = "PASSED" if success else "FAILED"
    icon = "✅" if success else "❌"

    model_block = ""
    if metadata:
        provider = metadata.get("provider", "")
        model = metadata.get("model", "")
        input_tokens = metadata.get("input_tokens", 0)
        output_tokens = metadata.get("output_tokens", 0)
        latency_ms = metadata.get("latency_ms", 0)

        model_block = (
            f"\n\n── Model ─────────────────────────────────────\n"
            f"Provider : {provider}\n"
            f"Model    : {model}\n"
            f"Tokens   : {input_tokens:,} in / {output_tokens:,} out\n"
            f"Latency  : {latency_ms:,} ms\n"
        )

    return (
        f"{icon} TEST {status}\n"
        f"File: {filepath}"
        f"{model_block}\n\n"
        f"── Playwright Output ──────────────────────────\n"
        f"{cleaned_output}\n\n"
    )


def format_healing_result(
    success: bool,
    attempt: int,
    max_retries: int,
    failure_type: str,
    confidence: float,
    strategy: str,
    hypothesis: str,
    metadata: Optional[dict] = None,
) -> str:
    """Format the healing pipeline result for the execution log panel.

    Args:
        success:      Whether healing succeeded.
        attempt:      Attempt number that succeeded (or last attempt if failed).
        max_retries:  Maximum attempts configured.
        failure_type: Classified failure type string.
        confidence:   Confidence score (0.0–1.0).
        strategy:     Repair strategy label.
        hypothesis:   LLM reasoning / hypothesis text.
        metadata:     Optional dict with provider, model, input_tokens,
                      output_tokens, latency_ms.

    Returns:
        str: Formatted result block.
    """
    icon = "✅" if success else "❌"
    status = "TEST HEALED" if success else "HEALING FAILED"

    model_block = ""
    if metadata:
        provider = metadata.get("provider", "")
        model = metadata.get("model", "")
        input_tokens = metadata.get("input_tokens", 0)
        output_tokens = metadata.get("output_tokens", 0)
        latency_ms = metadata.get("latency_ms", 0)

        model_block = (
            f"\n\n── Model ─────────────────────────────────────\n"
            f"Provider : {provider}\n"
            f"Model    : {model}\n"
            f"Tokens   : {input_tokens:,} in / {output_tokens:,} out\n"
            f"Latency  : {latency_ms:,} ms\n"
        )

    return (
        f"{icon} {status} — attempt {attempt}/{max_retries}\n"
        f"\n── Diagnosis ─────────────────────────────────\n"
        f"Failure type : {failure_type}\n"
        f"Confidence   : {int(confidence * 100)}%\n"
        f"Strategy     : {strategy}\n"
        f"{model_block}\n\n"
        f"── Reasoning ─────────────────────────────────\n"
        f"{hypothesis}\n\n"
    )
