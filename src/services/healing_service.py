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

from src.utils.formatting import format_healing_result

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
    from schemas.healing import (
        REPAIR_STRATEGY_LABELS,
        ExecutionTimeline,
        HealingAction,
        HealingDecision,
    )
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

    timeline_md = "### Healing Timeline\n\n"

    # --- Guard: no file ---
    if file_obj is None:
        _tracer.end_session(_trace_id, success=False)
        yield (
            "Please upload a test file.",
            _EXPLANATION_PENDING,
            timeline_md + "❌ No file uploaded",
            None,
        )
        return

    # --- Resolve and copy file to workspace ---
    try:
        file_path = file_obj if isinstance(file_obj, str) else file_obj.name
        local_path = os.path.join("tests", "generated", os.path.basename(file_path))
        validated_path = validate_file_path(local_path)
        shutil.copy(file_path, validated_path)

        timeline_md += f"→ File: `{os.path.basename(validated_path)}`\n\n"
        yield ("Initializing healing...", _EXPLANATION_PENDING, timeline_md, None)

    except ValidationError as exc:
        _tracer.end_session(_trace_id, success=False)
        yield (
            f"Validation Error: {exc}",
            _EXPLANATION_PENDING,
            timeline_md + f"❌ Validation error: {exc}",
            None,
        )
        return
    except Exception as exc:
        _tracer.end_session(_trace_id, success=False)
        yield (
            f"Error: {exc}",
            _EXPLANATION_PENDING,
            timeline_md + f"❌ Error: {exc}",
            None,
        )
        return

    # --- Initial test run ---
    timeline = ExecutionTimeline()
    timeline.add_step("Start", f"Healing session started for {validated_path}")

    timeline_md += "→ Initial run: executing test...\n\n"
    yield ("Running initial test...", _EXPLANATION_PENDING, timeline_md, None)

    result = run_test(validated_path)

    if result.passed:
        timeline.add_step("InitialRun", "Test passed, no healing needed")
        timeline_md += "✅ Initial run: passed — no healing needed\n\n"

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
    timeline_md += f"❌ Initial run: failed (exit code {result.returncode}) — beginning repair loop\n\n"
    yield ("Analyzing failure...", _EXPLANATION_PENDING, timeline_md, None)

    current_code = Path(validated_path).read_text(encoding="utf-8")
    latest_decision: Optional[HealingDecision] = None

    # --- Repair loop ---
    for attempt in range(int(max_retries)):
        attempt_num = attempt + 1

        timeline_md += f"→ Attempt {attempt_num}/{max_retries}: starting\n\n"
        timeline.add_step("HealingAttempt", f"Starting attempt {attempt_num}")
        yield (
            f"Healing attempt {attempt_num}...",
            _EXPLANATION_PENDING,
            timeline_md,
            None,
        )

        # Evidence
        timeline_md += f"→ Attempt {attempt_num}: collecting evidence\n\n"
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
        timeline_md += f"→ Attempt {attempt_num}: LLM call — classifying failure and selecting strategy\n\n"
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
            f"→ Attempt {attempt_num}: classifier={decision.failure_type.value if hasattr(decision.failure_type, 'value') else decision.failure_type}"
            f" confidence={int(decision.confidence_score * 100)}%"
            f" strategy={decision.action_taken.repair_strategy.value if hasattr(decision.action_taken.repair_strategy, 'value') else decision.action_taken.repair_strategy}\n\n"
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

            timeline_md += f"❌ Attempt {attempt_num}: repair could not be applied (code block not matched)\n\n"
            yield (
                f"Attempt {attempt_num} failed.",
                decision.to_markdown(),
                timeline_md,
                decision.to_dict(),
            )
            continue

        strategy_label = REPAIR_STRATEGY_LABELS.get(
            decision.action_taken.repair_strategy,
            str(decision.action_taken.repair_strategy),
        )
        timeline_md += f"→ Attempt {attempt_num}: {strategy_label} — writing patch\n\n"
        timeline.add_step(
            "RepairApplied",
            f"{strategy_label}: {decision.action_taken.description}",
        )
        yield (
            f"Attempt {attempt_num}: Saving changes...",
            _EXPLANATION_PENDING,
            timeline_md,
            None,
        )

        Path(validated_path).write_text(new_code, encoding="utf-8")

        # Verify
        timeline_md += f"→ Attempt {attempt_num}: verification run\n\n"
        yield (
            f"Attempt {attempt_num}: Verifying repair...",
            _EXPLANATION_PENDING,
            timeline_md,
            None,
        )

        verify_result = verify_repair(validated_path, decision)

        if decision.verification_passed:
            timeline.add_step("Verification", "Test passed on re-run")
            timeline_md += f"✅ Attempt {attempt_num}: verification passed — confidence={int(decision.confidence_score * 100)}%\n\n"
        else:
            timeline.add_step("Verification", "Test failed on re-run")
            timeline_md += f"❌ Attempt {attempt_num}: verification failed — confidence={int(decision.confidence_score * 100)}%\n\n"

        emit_artifacts(decision, timeline)

        if decision.verification_passed:
            _tracer.end_session(_trace_id, success=True)
            fail_type = (
                decision.failure_type.value
                if hasattr(decision.failure_type, "value")
                else str(decision.failure_type)
            )
            repair_strategy = (
                decision.action_taken.repair_strategy.value
                if hasattr(decision.action_taken.repair_strategy, "value")
                else str(decision.action_taken.repair_strategy)
            )
            result_text = format_healing_result(
                success=True,
                attempt=attempt_num,
                max_retries=int(max_retries),
                failure_type=fail_type,
                confidence=decision.confidence_score,
                strategy=repair_strategy,
                hypothesis=decision.hypothesis,
                metadata={
                    "provider": decision.provider or "",
                    "model": decision.model_used or "",
                    "input_tokens": decision.input_tokens or 0,
                    "output_tokens": decision.output_tokens or 0,
                    "latency_ms": decision.latency_ms or 0,
                },
            )
            yield (
                result_text,
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
    timeline_md += f"❌ All {max_retries} attempts exhausted — healing failed\n\n"
    _tracer.end_session(_trace_id, success=False)

    if latest_decision:
        fail_type = (
            latest_decision.failure_type.value
            if hasattr(latest_decision.failure_type, "value")
            else str(latest_decision.failure_type)
        )
        repair_strategy = (
            latest_decision.action_taken.repair_strategy.value
            if hasattr(latest_decision.action_taken.repair_strategy, "value")
            else str(latest_decision.action_taken.repair_strategy)
        )
        result_text = format_healing_result(
            success=False,
            attempt=int(max_retries),
            max_retries=int(max_retries),
            failure_type=fail_type,
            confidence=latest_decision.confidence_score,
            strategy=repair_strategy,
            hypothesis=latest_decision.hypothesis,
            metadata={
                "provider": latest_decision.provider or "",
                "model": latest_decision.model_used or "",
                "input_tokens": latest_decision.input_tokens or 0,
                "output_tokens": latest_decision.output_tokens or 0,
                "latency_ms": latest_decision.latency_ms or 0,
            },
        )
        md_report = latest_decision.to_markdown()
    else:
        result_text = "❌ HEALING FAILED\n\nNo repair was applied."
        md_report = "### Healing Failed"

    yield (
        result_text,
        md_report,
        timeline_md,
        latest_decision.to_dict() if latest_decision else None,
    )
