"""
JSONL trace writer — thread-safe append of span records to a file.

Each span is written as a single JSON line so the file is valid JSONL
and can be processed with ``jq``, ``grep``, or any streaming parser.

Example output line:
    {"span_type": "llm", "trace_id": "a1b2c3d4...", "model": "qwen3-coder-30b", ...}

Usage:
    writer = TraceWriter(Path("logs/traces.jsonl"))
    writer.write_span(some_pydantic_model)
"""

from __future__ import annotations

import threading
from pathlib import Path

from pydantic import BaseModel


class TraceWriter:
    """Appends Pydantic span records to a JSONL file, thread-safely.

    Args:
        output_path: Absolute or relative path to the ``.jsonl`` file.
                     The parent directory is created on first write if absent.
    """

    def __init__(self, output_path: Path) -> None:
        self._path = Path(output_path)
        self._lock = threading.Lock()

    @property
    def output_path(self) -> Path:
        """The path to the JSONL file."""
        return self._path

    def write_span(self, span: BaseModel) -> None:
        """Append a span to the JSONL file.

        Args:
            span: Any Pydantic ``BaseModel`` instance.  Serialised with
                  ``model_dump_json()`` (excludes unset defaults if ``exclude_unset``
                  were True, but here we keep all fields for full fidelity).

        This call is a no-op if the file cannot be written (e.g. read-only
        filesystem). Errors are swallowed so observability never breaks the
        main pipeline.
        """
        try:
            line = span.model_dump_json() + "\n"
            with self._lock:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(line)
        except Exception:
            # Observability must never break the main path.
            pass

    def read_all(self) -> list[dict]:
        """Read all spans from the JSONL file and return as a list of dicts.

        Useful for tests and tooling.  Returns an empty list if the file does
        not exist or is empty.
        """
        import json

        if not self._path.exists():
            return []
        spans = []
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        spans.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return spans
