"""
Self-healing agent for automatically repairing broken Playwright tests.
"""

import logging
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from schemas.healing import (
    Evidence,
    ExecutionTimeline,
    HealingAction,
    HealingAnalysis,
    HealingDecision,
)
from schemas.shared import FailureType, RunResult
from src.llm import get_default_router
from src.utils.browser import fetch_page_context
from src.utils.llm import parse_llm_response
from src.utils.prompt_loader import load_prompt
from src.utils.validation import validate_file_path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

ARTIFACTS_DIR = PROJECT_ROOT / "tests" / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def run_test(test_file) -> RunResult:
    """Run a Playwright test file and return a structured RunResult."""
    logger.info("Running %s...", test_file)
    try:
        result = subprocess.run(
            ["npx", "playwright", "test", str(test_file)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        return RunResult(
            returncode=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )
    except subprocess.TimeoutExpired:
        return RunResult.from_timeout()
    except FileNotFoundError:
        return RunResult.from_error("Playwright not found")


def extract_url_from_code(code: str) -> Optional[str]:
    """Extract the target URL from a page.goto() call in Playwright test code."""
    if not code:
        return None
    pattern = r"page\.goto\(['\"`](https?://[^\s'\"`]+)['\"`]\)"
    match = re.search(pattern, code)
    if match:
        return match.group(1)
    return None


def gather_evidence(test_file, result: RunResult) -> Evidence:
    """Collect evidence from a failed test run: logs, screenshot, DOM snippet."""
    logs = result.stderr if result.stderr else result.stdout

    # Look for the most recent screenshot in test-results/
    screenshot_path = None
    results_dir = PROJECT_ROOT / "test-results"
    if results_dir.exists():
        screenshots = list(results_dir.glob("**/*.png"))
        if screenshots:
            screenshot_path = str(max(screenshots, key=lambda p: p.stat().st_mtime))

    # Fetch live DOM from the target URL found in the test file
    dom_snippet = None
    try:
        test_file_path = Path(test_file)
        if test_file_path.exists():
            code = test_file_path.read_text(encoding="utf-8")
            url = extract_url_from_code(code)
            if url:
                logger.info("Fetching DOM context from %s...", url)
                dom_snippet = fetch_page_context(url)
                if dom_snippet and dom_snippet.startswith("Error"):
                    logger.warning("Failed to fetch DOM context: %s", dom_snippet)
                    dom_snippet = None
    except Exception as exc:
        logger.warning("Error gathering DOM context evidence: %s", exc)

    return Evidence(
        error_log=logs,
        screenshot_path=screenshot_path,
        dom_snippet=dom_snippet,
    )


def classify_failure_heuristic(logs: str) -> tuple[FailureType, float, str]:
    """Deterministically classify failure from log patterns.

    Returns:
        (FailureType, confidence, reasoning)
    """
    if not logs:
        return (FailureType.UNKNOWN, 0.0, "No logs available")

    if (
        "TimeoutError" in logs
        or "waiting for selector" in logs
        or "waiting for locator" in logs
        or "Test execution timed out" in logs
    ):
        return (
            FailureType.TIMEOUT,
            1.0,
            "Detected 'TimeoutError', 'waiting for selector', or 'waiting for locator' in logs",
        )

    if "TargetClosedError" in logs or "browser has been closed" in logs:
        return (
            FailureType.ENVIRONMENT_ISSUE,
            1.0,
            "Detected 'TargetClosedError' or browser crash",
        )

    if "expect(" in logs and "received" in logs:
        return (
            FailureType.ASSERTION_FAILED,
            1.0,
            "Detected 'expect(...)' assertion failure",
        )

    if "Error: strict mode violation" in logs:
        return (
            FailureType.LOCATOR_DRIFT,
            0.9,
            "Strict mode violation: multiple elements match selector",
        )

    if "locator resolved to 0 elements" in logs:
        if "Did you mean" in logs:
            return (
                FailureType.LOCATOR_DRIFT,
                0.8,
                "Locator failed but Playwright suggested content alternative",
            )
        return (FailureType.LOCATOR_NOT_FOUND, 0.7, "Locator resolved to 0 elements")

    if "net::ERR_ABORTED" in logs or "404" in logs or "500" in logs:
        return (
            FailureType.POTENTIAL_APP_DEFECT,
            0.8,
            "Detected network error or HTTP failure status code",
        )

    if "ReferenceError" in logs or "TypeError" in logs:
        return (
            FailureType.JAVASCRIPT_ERROR,
            0.7,
            "Detected JavaScript runtime error in logs",
        )

    return (FailureType.UNKNOWN, 0.0, "No specific pattern matched")


def analyze_and_plan(test_file, code: str, evidence: Evidence) -> HealingDecision:
    """Analyze a test failure with heuristics + LLM and produce a HealingDecision.

    The healer prompt receives the heuristic pre-diagnosis so the LLM can
    confirm or correct it.  The LLM response is validated with Pydantic
    (HealingAnalysis) before any field is accessed — no silent data corruption.

    Args:
        test_file: Path to the failing test file.
        code: Current source code of the failing test.
        evidence: Evidence collected from the failure run.

    Returns:
        HealingDecision: Validated diagnosis and proposed fix.
    """
    h_type, h_conf, h_reason = classify_failure_heuristic(evidence.error_log)

    system_prompt = load_prompt("healer").format(
        failure_type=h_type.value, confidence=h_conf, reason=h_reason
    )

    user_prompt_lines = [
        f"FILE: {test_file}",
        "",
        "BROKEN CODE:",
        "```typescript",
        code,
        "```",
        "",
        "ERROR LOGS:",
        evidence.error_log[:2000],
    ]
    if evidence.dom_snippet:
        user_prompt_lines.extend(
            [
                "",
                "PAGE DOM CONTEXT (CLEANED):",
                "```html",
                evidence.dom_snippet[:30000],
                "```",
            ]
        )
    user_prompt = "\n".join(user_prompt_lines)

    router = get_default_router()
    try:
        llm_response = router.complete_primary(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )

        raw_content = llm_response.content

        # --- Phase 1 core change: Pydantic validation replaces json.loads ---
        analysis = parse_llm_response(raw_content, HealingAnalysis)

        # Apply heuristic override: if heuristic is high-confidence and LLM
        # returned UNKNOWN, trust the heuristic.
        if h_conf > 0.8 and analysis.failure_type == FailureType.UNKNOWN:
            analysis = analysis.model_copy(update={"failure_type": h_type})

        return HealingDecision.from_analysis(
            test_file=str(test_file),
            analysis=analysis,
            evidence=evidence,
        )

    except Exception as exc:
        logger.error("LLM analysis error: %s", exc)
        return HealingDecision(
            test_file=str(test_file),
            failure_type=FailureType.UNKNOWN,
            failure_summary=f"Agent failed to analyze: {exc}",
            evidence=evidence,
            hypothesis="Fallback: manual intervention needed",
            confidence_score=0.0,
            reasoning_steps=["LLM call or response parsing failed"],
            action_taken=HealingAction(
                original_code="", fixed_code="", description="No action"
            ),
        )


def apply_fix(file_path, current_code: str, decision: HealingDecision) -> str:
    """Apply the proposed code fix using exact match with normalized fallback.

    Attempts exact string replacement first, then falls back to a
    sliding-window normalized match that tolerates indentation differences
    in LLM output.

    Args:
        file_path: Path to the file being modified (used only for logging).
        current_code: Current file content.
        decision: HealingDecision containing the original and fixed code.

    Returns:
        Updated code string, or current_code unchanged if no match was found.
    """
    target = decision.action_taken.original_code
    replacement = decision.action_taken.fixed_code

    if not target or not replacement:
        return current_code

    # Strategy 1: exact match
    if target in current_code and (
        len(replacement.splitlines()) == 1
        or (
            len(target.splitlines()) > 1
            and (len(target) - len(target.lstrip()))
            == (len(replacement) - len(replacement.lstrip()))
        )
    ):
        return current_code.replace(target, replacement)

    # Strategy 2: normalized line match (tolerates indentation drift)
    def normalize_lines(text: str):
        return [line.strip() for line in text.splitlines() if line.strip()]

    target_lines = normalize_lines(target)
    code_lines = current_code.splitlines()

    for i in range(len(code_lines) - len(target_lines) + 1):
        window = [line.strip() for line in code_lines[i : i + len(target_lines)]]
        if window == target_lines:
            # Infer base indentation from the first matched line
            base_indent = code_lines[i][
                : len(code_lines[i]) - len(code_lines[i].lstrip())
            ]

            # Determine the base indentation of the replacement block
            replacement_lines = replacement.splitlines()
            non_empty = [line for line in replacement_lines if line.strip()]
            rep_base = (
                len(non_empty[0]) - len(non_empty[0].lstrip()) if non_empty else 0
            )

            # Re-indent replacement to match the matched block's indentation
            indented = []
            for r_line in replacement_lines:
                if not r_line.strip():
                    indented.append("")
                else:
                    rel = max(0, (len(r_line) - len(r_line.lstrip())) - rep_base)
                    indented.append(base_indent + (" " * rel) + r_line.lstrip())

            new_lines = code_lines[:i] + indented + code_lines[i + len(target_lines) :]
            return "\n".join(new_lines)

    logger.warning(
        "Target code not found in file (exact or normalized).\nTarget:\n%s", target
    )
    return current_code


def emit_artifacts(decision: HealingDecision, timeline: ExecutionTimeline) -> None:
    """Write the healing decision and execution timeline to JSON artifact files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    decision_path = ARTIFACTS_DIR / f"healing_decision_{timestamp}.json"
    decision_path.write_text(decision.to_json(), encoding="utf-8")

    timeline_path = ARTIFACTS_DIR / f"execution_timeline_{timestamp}.json"
    timeline_path.write_text(timeline.to_json(), encoding="utf-8")

    logger.info("Artifacts saved:\n     %s\n     %s", decision_path, timeline_path)


def attempt_healing(test_file, max_retries: int = 3) -> str:
    """Orchestrate the full healing pipeline for a failing test file.

    Args:
        test_file: Path to the failing .spec.ts file.
        max_retries: Maximum number of repair attempts.

    Returns:
        A summary string describing the outcome.
    """
    timeline = ExecutionTimeline()
    timeline.add_step("Start", f"Healing session started for {test_file}")

    validated_path_str = validate_file_path(test_file)
    validated_path = Path(validated_path_str)
    if not validated_path.exists():
        msg = f"Error: File not found {validated_path}"
        timeline.add_step("Error", msg)
        return msg

    logger.info("--- Starting Healing Session: %s ---", test_file)

    # Initial run
    result = run_test(validated_path)
    if result.passed:
        timeline.add_step("InitialRun", "Test passed, no healing needed")
        success_decision = HealingDecision(
            test_file=str(test_file),
            failure_type=FailureType.UNKNOWN,
            failure_summary="Test passed initially",
            evidence=gather_evidence(validated_path, result),
            hypothesis="No repairs needed.",
            confidence_score=1.0,
            reasoning_steps=["Initial execution passed."],
            action_taken=HealingAction(
                original_code="", fixed_code="", description="None"
            ),
            verification_passed=True,
        )
        emit_artifacts(success_decision, timeline)
        logger.info("--- Healing Session Completed: Test passed initially ---")
        return "Test passed (No healing needed)."

    timeline.add_step(
        "FailureDetected",
        f"Initial test run failed with return code {result.returncode}",
    )

    current_code = validated_path.read_text(encoding="utf-8")

    for attempt in range(max_retries):
        logger.info("Healing Attempt %d/%d", attempt + 1, max_retries)
        timeline.add_step("HealingAttempt", f"Starting attempt {attempt + 1}")

        evidence = gather_evidence(validated_path, result)
        timeline.add_step(
            "EvidenceCollected", "Logs and screenshot (if available) collected"
        )

        decision = analyze_and_plan(validated_path, current_code, evidence)
        logger.info("Diagnosis: %s", decision.failure_type)
        logger.info("Hypothesis: %s", decision.hypothesis)
        timeline.add_step(
            "AnalysisComplete",
            f"Diagnosed as {decision.failure_type}. Hypothesis: {decision.hypothesis}",
        )

        new_code = apply_fix(validated_path, current_code, decision)
        if new_code == current_code:
            decision.verification_log = "Could not apply fix (code mismatch)"
            timeline.add_step(
                "ActionFailed",
                "Proposed fix could not be applied (target code not found)",
            )
            emit_artifacts(decision, timeline)
            continue

        timeline.add_step(
            "SelectorUpdated", f"Applied fix: {decision.action_taken.description}"
        )
        validated_path.write_text(new_code, encoding="utf-8")

        verify_result = run_test(validated_path)
        decision.verification_passed = verify_result.passed
        decision.verification_log = verify_result.output

        timeline.add_step(
            "Verification",
            "Test passed on re-run"
            if decision.verification_passed
            else "Test failed on re-run",
        )
        emit_artifacts(decision, timeline)

        if decision.verification_passed:
            logger.info("--- Healing Session Completed: SUCCESS ---")
            return f"\nSUCCESS: Test healed!\nReasoning: {decision.hypothesis}"

        current_code = new_code
        result = verify_result
        timeline.add_step("Retry", "Preparing for next retry attempt")

    timeline.add_step(
        "HealingFailed", f"Exhausted {max_retries} attempts without success"
    )
    logger.info(
        "--- Healing Session Completed: Failed after %d attempts ---", max_retries
    )
    return "Healing failed to make test pass."


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Self-healing agent for automatically repairing broken Playwright tests."
    )
    parser.add_argument(
        "test_file", type=str, help="Path to the broken Playwright test file."
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum healing attempts (default: 3).",
    )
    args = parser.parse_args()
    print(attempt_healing(args.test_file, max_retries=args.max_retries))
