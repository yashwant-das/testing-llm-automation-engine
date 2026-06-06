"""
Tracer — thread-local session management for structured span recording.

Design:
  - One session per thread (Gradio event handlers each run on their own thread).
  - Sessions are started explicitly with ``start_session(session_type)`` and
    closed with ``end_session(trace_id, success=...)``.
  - All instrumentation points (LLM router, subprocess runner) call
    ``record_llm_response()`` and ``record_subprocess()``; these are
    no-ops when no session is active on the calling thread.
  - ``NullTracer`` is the default global tracer — all methods are no-ops.

Thread safety:
  - ``threading.local()`` isolates session state per thread.
  - ``TraceWriter`` uses a ``threading.Lock()`` on the file write.
"""

from __future__ import annotations

import threading
import time
from typing import Optional, Union
from uuid import uuid4

from src.observability.schemas import (
    SessionSpan,
    SubprocessSpan,
    TraceMetadata,
    TraceSession,
)
from src.observability.writer import TraceWriter

_thread_local = threading.local()


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------


class Tracer:
    """Active tracer — records spans and writes them to a :class:`TraceWriter`.

    Do not instantiate directly; use :func:`src.observability.configure_tracer`.
    """

    def __init__(self, writer: TraceWriter) -> None:
        self._writer = writer

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_session(self, session_type: str) -> str:
        """Start a new trace session on the current thread.

        Stores the active :class:`TraceSession` in a thread-local so that
        subsequent ``record_*`` calls on the same thread are linked to this
        session automatically.

        Args:
            session_type: Label for the session (``"healing"``, ``"generation"``,
                          or ``"vision"``).

        Returns:
            A new unique ``trace_id`` string (32-char hex UUID).
        """
        trace_id = uuid4().hex
        _thread_local.session = TraceSession(
            trace_id=trace_id,
            session_type=session_type,
            start_monotonic=time.monotonic(),
        )
        _thread_local.prompt_version = ""
        _thread_local.prompt_hash = ""
        return trace_id

    def end_session(self, trace_id: str, *, success: bool) -> Optional[SessionSpan]:
        """Finalise the session and write a :class:`SessionSpan` to JSONL.

        Args:
            trace_id: Must match the ``trace_id`` returned by :meth:`start_session`.
                      If it does not match (or no session is active), this is a no-op.
            success:  Whether the session completed successfully.

        Returns:
            The written :class:`SessionSpan`, or ``None`` if no session was active.
        """
        session: Optional[TraceSession] = getattr(_thread_local, "session", None)
        if session is None or session.trace_id != trace_id:
            return None

        span = session.to_session_span(
            current_monotonic=time.monotonic(),
            success=success,
        )
        self._writer.write_span(span)
        _thread_local.session = None
        return span

    # ------------------------------------------------------------------
    # Prompt context
    # ------------------------------------------------------------------

    def set_prompt_context(self, prompt_version: str, prompt_hash: str) -> None:
        """Set the prompt name and hash for subsequent LLM call recordings.

        Call this immediately before the LLM call that uses the prompt, so that
        the prompt metadata is attached to the correct :class:`TraceMetadata` span.

        Args:
            prompt_version: Human-readable prompt name / version (e.g. ``"healer"``).
            prompt_hash:    SHA-256 hex prefix of the prompt content.
        """
        _thread_local.prompt_version = prompt_version
        _thread_local.prompt_hash = prompt_hash

    # ------------------------------------------------------------------
    # Span recording
    # ------------------------------------------------------------------

    def record_llm_response(self, response) -> Optional[TraceMetadata]:
        """Record an LLM call span from an :class:`~src.llm.router.LLMResponse`.

        This is a no-op when no session is active on the current thread.

        Args:
            response: An ``LLMResponse`` (duck-typed to avoid a circular import —
                      must have ``model_used``, ``provider``, ``input_tokens``,
                      ``output_tokens``, ``latency_ms``, ``retry_count``).

        Returns:
            The recorded :class:`TraceMetadata` span, or ``None`` if no session
            is active.
        """
        session: Optional[TraceSession] = getattr(_thread_local, "session", None)
        if session is None:
            return None

        span = TraceMetadata(
            trace_id=session.trace_id,
            operation_id=uuid4().hex[:8],
            model=getattr(response, "model_used", "unknown"),
            model_version="",
            prompt_version=getattr(_thread_local, "prompt_version", ""),
            prompt_hash=getattr(_thread_local, "prompt_hash", ""),
            input_tokens=getattr(response, "input_tokens", 0),
            output_tokens=getattr(response, "output_tokens", 0),
            latency_ms=getattr(response, "latency_ms", 0),
            retry_count=getattr(response, "retry_count", 0),
            failure_reason=None,
        )
        session.llm_spans.append(span)
        self._writer.write_span(span)
        return span

    def record_subprocess(
        self,
        *,
        command: str,
        exit_code: int,
        latency_ms: int,
    ) -> Optional[SubprocessSpan]:
        """Record a subprocess call span.

        This is a no-op when no session is active on the current thread.

        Args:
            command:    The command that was executed (string label).
            exit_code:  Process exit code (0 = success).
            latency_ms: Wall-clock duration of the subprocess call.

        Returns:
            The recorded :class:`SubprocessSpan`, or ``None`` if no session
            is active.
        """
        session: Optional[TraceSession] = getattr(_thread_local, "session", None)
        if session is None:
            return None

        span = SubprocessSpan(
            trace_id=session.trace_id,
            operation_id=uuid4().hex[:8],
            command=command,
            exit_code=exit_code,
            latency_ms=latency_ms,
            success=(exit_code == 0),
        )
        session.subprocess_spans.append(span)
        self._writer.write_span(span)
        return span

    # ------------------------------------------------------------------
    # Session inspection
    # ------------------------------------------------------------------

    def get_session(self, trace_id: str) -> Optional[TraceSession]:
        """Return the active :class:`TraceSession` for this thread if ``trace_id`` matches.

        Returns ``None`` if no session is active or the IDs do not match.
        Useful for assertions in tests.
        """
        session: Optional[TraceSession] = getattr(_thread_local, "session", None)
        if session is not None and session.trace_id == trace_id:
            return session
        return None


# ---------------------------------------------------------------------------
# NullTracer
# ---------------------------------------------------------------------------


class NullTracer:
    """No-op tracer — safe to call when observability is disabled.

    All methods are no-ops and return ``None`` / empty strings.  Used as the
    default global tracer so that instrumentation points in the router and
    subprocess runner never need to guard against an uninitialised tracer.
    """

    def start_session(self, session_type: str) -> str:
        return ""

    def set_prompt_context(self, prompt_version: str, prompt_hash: str) -> None:
        pass

    def record_llm_response(self, response) -> None:
        return None

    def record_subprocess(
        self,
        *,
        command: str,
        exit_code: int,
        latency_ms: int,
    ) -> None:
        return None

    def end_session(self, trace_id: str, *, success: bool) -> None:
        return None

    def get_session(self, trace_id: str) -> None:
        return None
