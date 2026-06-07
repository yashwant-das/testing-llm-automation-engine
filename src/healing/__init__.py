"""
Self-healing package — decomposed modules for the Playwright test repair pipeline.

Public API (import from here or from the individual modules):

    run_test                  runner.run_test
    extract_url_from_code     evidence.extract_url_from_code
    gather_evidence           evidence.gather_evidence
    classify_failure_heuristic  classifier.classify_failure_heuristic
    analyze_and_plan          planner.analyze_and_plan
    apply_fix                 repair.apply_fix
    verify_repair             verifier.verify_repair
    emit_artifacts            artifact_store.emit_artifacts
    attempt_healing           non-streaming CLI orchestrator (defined here)

The streaming UI orchestrator lives in src.services.healing_service.
"""

from src.healing.artifact_store import emit_artifacts
from src.healing.classifier import classify_failure_heuristic
from src.healing.evidence import extract_url_from_code, gather_evidence
from src.healing.planner import analyze_and_plan
from src.healing.repair import apply_fix
from src.healing.runner import run_test
from src.healing.verifier import verify_repair

__all__ = [
    "run_test",
    "extract_url_from_code",
    "gather_evidence",
    "classify_failure_heuristic",
    "analyze_and_plan",
    "apply_fix",
    "verify_repair",
    "emit_artifacts",
    "attempt_healing",
]


def attempt_healing(test_file, max_retries: int = 3) -> str:
    """Orchestrate the full healing pipeline for a failing test file.

    Non-streaming version intended for CLI use (``python -m src.healing``).
    The streaming Gradio version lives in src.services.healing_service.

    Starts and ends a tracer session so CLI runs produce the same spans as
    UI runs.  If no tracer has been configured, NullTracer no-ops all calls.

    Args:
        test_file:   Path to the failing .spec.ts file.
        max_retries: Maximum number of repair attempts.

    Returns:
        A summary string describing the final outcome.
    """
    import logging
    from pathlib import Path

    from schemas.healing import (
        REPAIR_STRATEGY_LABELS,
        ExecutionTimeline,
        HealingAction,
        HealingDecision,
    )
    from schemas.shared import FailureType
    from src.observability import get_tracer
    from src.utils.validation import validate_file_path

    logger = logging.getLogger(__name__)
    tracer = get_tracer()
    trace_id = tracer.start_session("healing")
    _success = False

    try:
        timeline = ExecutionTimeline()
        timeline.add_step("Start", f"Healing session started for {test_file}")

        validated_path_str = validate_file_path(test_file)
        validated_path = Path(validated_path_str)
        if not validated_path.exists():
            msg = f"Error: File not found {validated_path}"
            timeline.add_step("Error", msg)
            return msg

        logger.info("--- Starting Healing Session: %s ---", test_file)

        # --- Initial run ---
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
            _success = True
            return "Test passed (No healing needed)."

        timeline.add_step(
            "FailureDetected",
            f"Initial test run failed with return code {result.returncode}",
        )

        current_code = validated_path.read_text(encoding="utf-8")

        # --- Repair loop ---
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

            strategy_label = REPAIR_STRATEGY_LABELS.get(
                decision.action_taken.repair_strategy,
                str(decision.action_taken.repair_strategy),
            )
            timeline.add_step(
                "RepairApplied",
                f"{strategy_label}: {decision.action_taken.description}",
            )
            validated_path.write_text(new_code, encoding="utf-8")

            result = verify_repair(validated_path, decision)

            timeline.add_step(
                "Verification",
                "Test passed on re-run"
                if decision.verification_passed
                else "Test failed on re-run",
            )
            emit_artifacts(decision, timeline)

            if decision.verification_passed:
                logger.info("--- Healing Session Completed: SUCCESS ---")
                _success = True
                return f"\nSUCCESS: Test healed!\nReasoning: {decision.hypothesis}"

            current_code = new_code
            timeline.add_step("Retry", "Preparing for next retry attempt")

        # --- Exhausted all attempts ---
        timeline.add_step(
            "HealingFailed", f"Exhausted {max_retries} attempts without success"
        )
        logger.info(
            "--- Healing Session Completed: Failed after %d attempts ---", max_retries
        )
        return "Healing failed to make test pass."

    finally:
        tracer.end_session(trace_id, success=_success)
