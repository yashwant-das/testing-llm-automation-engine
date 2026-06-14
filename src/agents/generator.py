"""
Test generation agent for creating Playwright test scripts.

Generates TypeScript Playwright tests from a URL and feature description
by fetching page context and calling an LLM.  The LLM response is validated
through GenerationResult before returning.

generate_test_script() returns a GenerationDecision carrying the full
provenance record (model, tokens, latency, context snapshot used).
"""

import hashlib
import logging

from schemas.generation import GenerationDecision, GenerationResult
from src.llm import get_default_router
from src.utils.llm import extract_code_block
from src.utils.prompt_loader import get_prompt_hash, get_prompt_version, load_prompt

logger = logging.getLogger(__name__)

TEST_DIR = "tests/generated"


def generate_test_script(url: str, feature_description: str) -> GenerationDecision:
    """Generate a Playwright test script from a URL and feature description.

    Args:
        url: Validated URL string.
        feature_description: Validated feature description string.

    Returns:
        GenerationDecision carrying the generated code and full provenance.

    Raises:
        ValueError: If the LLM returns empty or invalid code.
        Exception:  On LLM connectivity or context-collection failures.
    """
    logger.info("Generating test for URL: %s", url)

    from src.context import collect_context

    snapshot = collect_context(url, capture_html=True, capture_a11y=True)

    if not snapshot.html and not snapshot.accessibility_tree:
        raise ValueError(f"Failed to fetch page context from {url}")

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

    prompt_version = get_prompt_version("generator")
    prompt_hash = get_prompt_hash("generator")
    system_instruction = load_prompt("generator")
    user_prompt = f"""
TARGET URL: {url}
USER STORY: {feature_description}
PAGE CONTEXT: {html_context}
"""

    router = get_default_router()
    llm_response = router.complete_primary(
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )

    if not llm_response.content:
        raise ValueError("LLM returned empty response")

    extracted = extract_code_block(llm_response.content)
    result = GenerationResult(code=extracted)

    snapshot_id = hashlib.sha256((snapshot.html or "").encode("utf-8")).hexdigest()[:12]

    return GenerationDecision(
        url=url,
        story=feature_description,
        code=result.code,
        line_count=result.line_count,
        context_snapshot=snapshot,
        model_used=llm_response.model_used,
        provider=llm_response.provider,
        prompt_version=prompt_version,
        prompt_hash=prompt_hash,
        input_tokens=llm_response.input_tokens,
        output_tokens=llm_response.output_tokens,
        latency_ms=llm_response.latency_ms,
        retry_count=llm_response.retry_count,
        context_snapshot_id=snapshot_id,
    )
