"""
Healing service — self-healing pipeline with streaming progress for Gradio.

heal_test_streaming  accepts a Gradio file object or path string and runs
                     the full healing loop, yielding progress tuples at
                     each significant stage.

Yield shape: (result_text, explanation_md, timeline_md, decision_dict_or_None)
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Placeholders for intermediate yields where the explanation panel is not yet ready
_EXPLANATION_PENDING = "### 🧠 AI Healing Explanation\n*No healer run active.*"


def heal_test_streaming(
    file_obj, max_retries: int
) -> Iterator[tuple[str, str, str, Optional[dict]]]:
    """Run the full self-healing pipeline for an uploaded test file.

    Handles Gradio file object resolution, workspace copy, and the multi-attempt
    repair loop.  All agent imports happen inside this function so the module
    can be imported without triggering agent initialisation.

    Args:
        file_obj:    Gradio file object (has a .name attribute) or a path string.
                     May be None if the user did not upload a file.
        max_retries: Maximum number of repair attempts.

    Yields:
        (result_text, explanation_markdown, timeline_markdown, decision_dict_or_None)
    """
    from schemas.healing import ExecutionTimeline, HealingAction, HealingDecision
    from schemas.shared import FailureType
    from src.healing import (
        analyze_and_plan,
        apply_fix,
        emit_artifacts,
        gather_evidence,
        run_test,
        verify_repair,
    )
    from src.observability import get_tracer
    from src.utils.validation import ValidationError, validate_file_path

    _tracer = get_tracer()
    _trace_id = _tracer.start_session("healing")

    timeline_md = "### ⏱️ Healing Process Timeline\n\n"

    # --- Guard: no file ---
    if file_obj is None:
        _tracer.end_session(_trace_id, success=False)
        yield (
            "Please upload a test file.",
            _EXPLANATION_PENDING,
            timeline_md + "🔴 **No file uploaded**",
            None,
        )
        return

    # --- Resolve and copy file to workspace ---
    try:
        file_path = file_obj if isinstance(file_obj, str) else file_obj.name
        local_path = os.path.join("tests", "generated", os.path.basename(file_path))
        validated_path = validate_file_path(local_path)
        shutil.copy(file_path, validated_path)

        timeline_md += (
            f"🟢 **File Uploaded**: Saved to workspace path "
            f"`{os.path.basename(validated_path)}`...\n\n"
        )
        yield ("Initializing healing...", _EXPLANATION_PENDING, timeline_md, None)

    except ValidationError as exc:
        _tracer.end_session(_trace_id, success=False)
        yield (
            f"Validation Error: {exc}",
            _EXPLANATION_PENDING,
            timeline_md + f"🔴 **Validation Error**: {exc}",
            None,
        )
        return
    except Exception as exc:
        _tracer.end_session(_trace_id, success=False)
        yield (
            f"Error: {exc}",
            _EXPLANATION_PENDING,
            timeline_md + f"🔴 **Error**: {exc}",
            None,
        )
        return

    # --- Initial test run ---
    timeline = ExecutionTimeline()
    timeline.add_step("Start", f"Healing session started for {validated_path}")

    timeline_md += "🟢 **Initial Verification Run**: Launching test to capture failure signature...\n\n"
    yield ("Running initial test...", _EXPLANATION_PENDING, timeline_md, None)

    result = run_test(validated_path)

    if result.passed:
        timeline.add_step("InitialRun", "Test passed, no healing needed")
        timeline_md += "✅ **No Healing Needed**: Test passed on the first run!\n\n"

        evidence = gather_evidence(validated_path, result)
        success_decision = HealingDecision(
            test_file=validated_path,
            failure_type=FailureType.UNKNOWN,
            failure_summary="Test passed initially",
            evidence=evidence,
            hypothesis="No repairs needed.",
            confidence_score=1.0,
            reasoning_steps=["Initial execution passed."],
            action_taken=HealingAction(
                original_code="", fixed_code="", description="None"
            ),
            verification_passed=True,
        )
        emit_artifacts(success_decision, timeline)
        _tracer.end_session(_trace_id, success=True)

        yield (
            "Test passed (No healing needed).",
            success_decision.to_markdown(),
            timeline_md,
            success_decision.to_dict(),
        )
        return

    timeline.add_step(
        "FailureDetected",
        f"Initial test run failed with return code {result.returncode}",
    )
    timeline_md += (
        f"❌ **Failure Detected**: Test failed (exit code {result.returncode}). "
        f"Gaining diagnostic context...\n\n"
    )
    yield ("Analyzing failure...", _EXPLANATION_PENDING, timeline_md, None)

    current_code = Path(validated_path).read_text(encoding="utf-8")
    latest_decision: Optional[HealingDecision] = None

    # --- Repair loop ---
    for attempt in range(int(max_retries)):
        attempt_num = attempt + 1

        timeline_md += f"🟢 **Attempt {attempt_num}/{max_retries}**: Initiating healing attempt...\n\n"
        timeline.add_step("HealingAttempt", f"Starting attempt {attempt_num}")
        yield (
            f"Healing attempt {attempt_num}...",
            _EXPLANATION_PENDING,
            timeline_md,
            None,
        )

        # Evidence
        timeline_md += (
            f"🟢 **Evidence Gathering (Attempt {attempt_num})**: "
            f"Loading logs, screenshot, and page HTML DOM...\n\n"
        )
        yield (
            f"Attempt {attempt_num}: Gathering evidence...",
            _EXPLANATION_PENDING,
            timeline_md,
            None,
        )
        evidence = gather_evidence(validated_path, result)
        timeline.add_step(
            "EvidenceCollected", "Logs and screenshot (if available) collected"
        )

        # Diagnose
        timeline_md += (
            f"🧠 **AI Diagnostic Reasoning (Attempt {attempt_num})**: "
            f"Synthesizing failure classification and resolution strategy...\n\n"
        )
        yield (
            f"Attempt {attempt_num}: Reasoning and planning...",
            _EXPLANATION_PENDING,
            timeline_md,
            None,
        )

        try:
            from src.utils.prompt_loader import get_prompt_hash

            _tracer.set_prompt_context("healer", get_prompt_hash("healer"))
        except Exception:
            pass

        decision = analyze_and_plan(validated_path, current_code, evidence)
        latest_decision = decision
        timeline.add_step(
            "AnalysisComplete",
            f"Diagnosed as {decision.failure_type}. Hypothesis: {decision.hypothesis}",
        )

        timeline_md += (
            f'🧠 **AI Hypothesis**: *"{decision.hypothesis}"* '
            f"(Confidence: {int(decision.confidence_score * 100)}%)\n\n"
        )
        yield (
            f"Attempt {attempt_num}: Proposing code repair...",
            _EXPLANATION_PENDING,
            timeline_md,
            None,
        )

        # Apply fix
        new_code = apply_fix(validated_path, current_code, decision)

        if new_code == current_code:
            decision.verification_log = "Could not apply fix (code mismatch)"
            timeline.add_step(
                "ActionFailed",
                "Proposed fix could not be applied (target code not found)",
            )
            emit_artifacts(decision, timeline)

            timeline_md += "🔴 **Apply Repair Failed**: Match block indentation/whitespace mismatch.\n\n"
            yield (
                f"Attempt {attempt_num} failed.",
                decision.to_markdown(),
                timeline_md,
                decision.to_dict(),
            )
            continue

        timeline_md += (
            f"🛠️ **Repair Applied**: Selector replaced: "
            f'*"{decision.action_taken.description}"*...\n\n'
        )
        timeline.add_step(
            "SelectorUpdated",
            f"Applied fix: {decision.action_taken.description}",
        )
        yield (
            f"Attempt {attempt_num}: Saving changes...",
            _EXPLANATION_PENDING,
            timeline_md,
            None,
        )

        Path(validated_path).write_text(new_code, encoding="utf-8")

        # Verify
        timeline_md += (
            f"🟢 **Verification Run (Attempt {attempt_num})**: "
            f"Re-running test script inside workspace...\n\n"
        )
        yield (
            f"Attempt {attempt_num}: Verifying repair...",
            _EXPLANATION_PENDING,
            timeline_md,
            None,
        )

        verify_result = verify_repair(validated_path, decision)

        if decision.verification_passed:
            timeline.add_step("Verification", "Test passed on re-run")
            timeline_md += "✅ **Verification Passed**: Repaired test successfully verified on re-run!\n\n"
        else:
            timeline.add_step("Verification", "Test failed on re-run")
            timeline_md += (
                "❌ **Verification Failed**: Test failed again on re-run.\n\n"
            )

        emit_artifacts(decision, timeline)

        if decision.verification_passed:
            _tracer.end_session(_trace_id, success=True)
            yield (
                f"SUCCESS: Test healed!\nReasoning: {decision.hypothesis}",
                decision.to_markdown(),
                timeline_md,
                decision.to_dict(),
            )
            return

        current_code = new_code
        result = verify_result
        timeline.add_step("Retry", "Preparing for next retry attempt")

    # --- Exhausted all attempts ---
    timeline.add_step(
        "HealingFailed", f"Exhausted {max_retries} attempts without success"
    )
    timeline_md += "🔴 **Healing Failed**: Bounded execution limit reached without achieving verification pass.\n\n"
    _tracer.end_session(_trace_id, success=False)

    md_report = (
        latest_decision.to_markdown() if latest_decision else "### Healing Failed"
    )
    yield (
        "Healing failed to make test pass.",
        md_report,
        timeline_md,
        latest_decision.to_dict() if latest_decision else None,
    )
