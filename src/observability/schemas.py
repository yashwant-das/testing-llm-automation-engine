"""
Observability span schemas — Pydantic models for structured trace records.

Three span types:
  TraceMetadata   — one LLM call (model, tokens, latency, retry_count, prompt)
  SubprocessSpan  — one Playwright subprocess invocation
  SessionSpan     — end-to-end session aggregating all child spans

All spans share a ``trace_id`` that links them to a parent session, and an
``operation_id`` that uniquely identifies the individual span.

``TraceMetadata`` is also exported from ``schemas/artifacts.py`` (the canonical
location per the modernisation plan).  This module re-exports it for convenience
so that ``src/observability`` code only needs to import from this module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Re-export canonical TraceMetadata from schemas/artifacts (plan requirement)
# ---------------------------------------------------------------------------
from schemas.artifacts import TraceMetadata  # noqa: F401 — re-export

__all__ = [
    "TraceMetadata",
    "SubprocessSpan",
    "SessionSpan",
    "TraceSession",
]


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# SubprocessSpan
# ---------------------------------------------------------------------------


class SubprocessSpan(BaseModel):
    """Span recording a single Playwright subprocess call."""

    span_type: Literal["subprocess"] = "subprocess"
    trace_id: str
    operation_id: str
    command: str = Field(
        description="The command that was run (e.g. 'npx playwright test foo.spec.ts')."
    )
    exit_code: int
    latency_ms: int = Field(ge=0)
    success: bool
    timestamp: str = Field(default_factory=_now_iso)


# ---------------------------------------------------------------------------
# SessionSpan
# ---------------------------------------------------------------------------


class SessionSpan(BaseModel):
    """Aggregated span for a complete healing / generation / vision session."""

    span_type: Literal["session"] = "session"
    trace_id: str
    session_type: str = Field(description="'healing', 'generation', or 'vision'.")
    total_latency_ms: int = Field(
        ge=0, description="Wall-clock duration of the full session."
    )
    llm_call_count: int = Field(ge=0)
    subprocess_call_count: int = Field(ge=0)
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    total_retry_count: int = Field(ge=0)
    success: bool
    timestamp: str = Field(default_factory=_now_iso)


# ---------------------------------------------------------------------------
# TraceSession (in-memory accumulator — not written to JSONL)
# ---------------------------------------------------------------------------


class TraceSession(BaseModel):
    """In-memory accumulator for all spans in a single session.

    Not written to JSONL directly — :meth:`to_session_span` produces the
    summary span that is written when the session ends.
    """

    trace_id: str
    session_type: str
    llm_spans: List[TraceMetadata] = Field(default_factory=list)
    subprocess_spans: List[SubprocessSpan] = Field(default_factory=list)
    start_monotonic: float = Field(description="time.monotonic() at session start.")

    def to_session_span(
        self, *, current_monotonic: float, success: bool
    ) -> SessionSpan:
        """Produce the summary SessionSpan for this session.

        Args:
            current_monotonic: ``time.monotonic()`` at session end.
            success:           Whether the session succeeded.

        Returns:
            :class:`SessionSpan` with aggregated totals.
        """
        elapsed_ms = max(0, int((current_monotonic - self.start_monotonic) * 1000))
        total_input = sum(s.input_tokens for s in self.llm_spans)
        total_output = sum(s.output_tokens for s in self.llm_spans)
        total_retries = sum(s.retry_count for s in self.llm_spans)
        return SessionSpan(
            trace_id=self.trace_id,
            session_type=self.session_type,
            total_latency_ms=elapsed_ms,
            llm_call_count=len(self.llm_spans),
            subprocess_call_count=len(self.subprocess_spans),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_retry_count=total_retries,
            success=success,
        )
