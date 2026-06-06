"""
Healing planner — heuristic pre-diagnosis + LLM reasoning → HealingDecision.

Single responsibility: given the test file path, its source code, and the
collected evidence, produce a HealingDecision that contains the diagnosed
failure type, hypothesis, and the proposed code swap.

The planner:
  1. Runs the heuristic classifier for a fast pre-diagnosis.
  2. Builds a prompt that includes the pre-diagnosis, the broken code, the
     error logs, and the live DOM snippet (when available).
  3. Calls the LLM via LLMRouter.complete_primary().
  4. Validates the response with parse_llm_response(HealingAnalysis).
  5. Optionally overrides an LLM "UNKNOWN" with the heuristic type when the
     heuristic confidence is > 0.8.
  6. Returns a safe fallback HealingDecision on any LLM/parsing error so the
     healing loop always gets a valid object.
"""

import logging

from schemas.healing import Evidence, HealingAction, HealingAnalysis, HealingDecision
from schemas.shared import FailureType
from src.healing.classifier import classify_failure_heuristic
from src.llm import get_default_router
from src.utils.llm import parse_llm_response
from src.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


def analyze_and_plan(test_file, code: str, evidence: Evidence) -> HealingDecision:
    """Analyze a test failure with heuristics + LLM and produce a HealingDecision.

    Args:
        test_file: Path to the failing test file (used in the prompt and stored
                   in the decision).
        code:      Current source code of the failing test.
        evidence:  Evidence collected from the failure run.

    Returns:
        HealingDecision with a validated diagnosis and proposed code fix.
        Falls back to a zero-confidence decision if the LLM call or parsing fails.
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

        # Pydantic validation — no silent data corruption (Phase 1 core change)
        analysis = parse_llm_response(raw_content, HealingAnalysis)

        # Heuristic override: trust high-confidence heuristic over LLM UNKNOWN
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
