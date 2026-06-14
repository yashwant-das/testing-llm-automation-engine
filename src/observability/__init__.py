"""
Observability package — structured span recording for LLM calls and subprocess invocations.

Zero-dependency JSONL tracer.  All spans written to ``logs/traces.jsonl``
as newline-delimited JSON, queryable with ``jq``.

Usage (production):
    from src.observability import configure_tracer, get_tracer

    # At application startup (optional — defaults to NullTracer):
    configure_tracer()

    # In a healing session:
    tracer = get_tracer()
    trace_id = tracer.start_session("healing")
    ...
    tracer.end_session(trace_id, success=True)

Usage (testing / disabled):
    from src.observability import get_tracer
    get_tracer().start_session("healing")  # NullTracer no-ops all calls

Public API:
    configure_tracer(output_dir)   — initialise the global tracer (returns Tracer)
    get_tracer()                   — return current global tracer (NullTracer by default)
    Tracer                         — active tracer class
    NullTracer                     — no-op tracer (safe to use when observability is off)
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from src.observability.tracer import NullTracer, Tracer
from src.observability.writer import TraceWriter

__all__ = [
    "configure_tracer",
    "get_tracer",
    "NullTracer",
    "Tracer",
]

# Global singleton — NullTracer by default so all instrumentation points
# are safe to call before configure_tracer() has been invoked.
_tracer: Union[Tracer, NullTracer] = NullTracer()


def get_tracer() -> Union[Tracer, NullTracer]:
    """Return the current global tracer.

    Returns a :class:`NullTracer` until :func:`configure_tracer` is called.
    All methods on ``NullTracer`` are no-ops, so instrumentation code never
    needs to guard against an uninitialised tracer.
    """
    return _tracer


def configure_tracer(output_dir: Path | None = None) -> Tracer:
    """Initialise the global tracer and return it.

    Args:
        output_dir: Directory for ``traces.jsonl``.  Defaults to ``logs/``
                    relative to the current working directory.  Created if absent.

    Returns:
        The newly configured :class:`Tracer` instance (also stored globally).
    """
    global _tracer
    if output_dir is None:
        output_dir = Path("logs")
    writer = TraceWriter(Path(output_dir) / "traces.jsonl")
    _tracer = Tracer(writer)
    return _tracer
