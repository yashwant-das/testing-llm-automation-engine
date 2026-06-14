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

import hashlib
import logging
import time

from schemas.healing import Evidence, HealingAction, HealingAnalysis, HealingDecision
from schemas.shared import FailureType
from src.healing.classifier import classify_failure_heuristic
from src.llm import get_default_router
from src.utils.llm import parse_llm_response
from src.utils.prompt_loader import get_prompt_hash, get_prompt_version, load_prompt

logger = logging.getLogger(__name__)


def _evidence_snapshot_id(evidence: Evidence) -> str:
    """Return a short stable ID for the evidence error_log.

    Used as ``context_snapshot_id`` so healing decisions can be cross-referenced
    even when no formal snapshot was stored.  First 12 hex chars of SHA-256.
    """
    content = evidence.error_log or ""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


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
    t0 = time.monotonic()
    h_type, h_conf, h_reason = classify_failure_heuristic(evidence.error_log)

    _prompt_version = get_prompt_version("healer")
    _prompt_hash = get_prompt_hash("healer")
    _snapshot_id = _evidence_snapshot_id(evidence)

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
    if evidence.accessibility_tree:
        user_prompt_lines.extend(
            [
                "",
                "ACCESSIBILITY TREE (use roles/names for locators):",
                evidence.accessibility_tree[:5000],
            ]
        )
    if evidence.locator_candidates:
        cand_lines = "\n".join(f"  - {c}" for c in evidence.locator_candidates[:20])
        user_prompt_lines.extend(
            [
                "",
                "AVAILABLE LOCATORS (from accessibility tree, prefer these):",
                cand_lines,
            ]
        )
    if evidence.console_errors:
        err_lines = "\n".join(evidence.console_errors[:5])
        user_prompt_lines.extend(
            [
                "",
                "BROWSER CONSOLE ERRORS:",
                err_lines,
            ]
        )
    if evidence.network_errors:
        net_lines = "\n".join(evidence.network_errors[:5])
        user_prompt_lines.extend(
            [
                "",
                "FAILED NETWORK REQUESTS:",
                net_lines,
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

        # Pydantic validation — no silent data corruption
        analysis = parse_llm_response(raw_content, HealingAnalysis)

        # Heuristic override: trust high-confidence heuristic over LLM UNKNOWN
        if h_conf > 0.8 and analysis.failure_type == FailureType.UNKNOWN:
            analysis = analysis.model_copy(update={"failure_type": h_type})

        duration_ms = int((time.monotonic() - t0) * 1000)
        return HealingDecision.from_analysis(
            test_file=str(test_file),
            analysis=analysis,
            evidence=evidence,
            model_used=llm_response.model_used,
            provider=llm_response.provider,
            prompt_version=_prompt_version,
            prompt_hash=_prompt_hash,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
            latency_ms=duration_ms,
            retry_count=llm_response.retry_count,
            context_snapshot_id=_snapshot_id,
        )

    except Exception as exc:
        logger.error("LLM analysis error: %s", exc)
        duration_ms = int((time.monotonic() - t0) * 1000)
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
            prompt_version=_prompt_version,
            prompt_hash=_prompt_hash,
            latency_ms=duration_ms,
            context_snapshot_id=_snapshot_id,
        )
