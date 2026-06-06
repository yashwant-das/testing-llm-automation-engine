"""
Pydantic schemas for context snapshots and artifact records.

Phase 6 (Context Collection Modernization): ContextSnapshot is now fully
implemented via ``src.context.collect_context()``.  The schema itself is
unchanged from the Phase 1 stub — all fields were already defined correctly.

Phase 8 (Observability): TraceMetadata records per-LLM-call observability data
(model, tokens, latency, retry_count, prompt hash).
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TraceMetadata(BaseModel):
    """Per-LLM-call observability record.

    Recorded by ``src.observability.Tracer`` after every successful or failed
    LLM call through ``LLMRouter``.  Linked to its parent session via
    ``trace_id``.

    Phase 8 addition.
    """

    span_type: str = "llm"
    trace_id: str
    operation_id: str = Field(description="Unique ID for this individual span.")
    model: str
    model_version: str = ""
    prompt_version: str = Field(
        default="",
        description="Prompt name / version string (e.g. 'healer').",
    )
    prompt_hash: str = Field(
        default="",
        description="SHA-256 hex prefix of the prompt content.",
    )
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    failure_reason: Optional[str] = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
    )


class ContextSnapshot(BaseModel):
    """
    Unified context snapshot collected before generation or healing.

    Phase 1 stub: only HTML is collected. Phase 6 will expand this with
    accessibility tree, console errors, network failures, and locator
    candidates — without changing the interface.
    """

    url: str
    html: Optional[str] = None
    accessibility_tree: Optional[str] = None
    console_errors: List[str] = Field(default_factory=list)
    network_errors: List[str] = Field(default_factory=list)
    locator_candidates: List[str] = Field(default_factory=list)
    screenshot_path: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    @property
    def has_html(self) -> bool:
        return bool(self.html)

    @property
    def has_a11y_tree(self) -> bool:
        return bool(self.accessibility_tree)

    @property
    def is_empty(self) -> bool:
        """True when neither HTML nor accessibility tree was collected."""
        return not self.html and not self.accessibility_tree
